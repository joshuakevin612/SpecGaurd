"""Account sessions and durable, single-server quotas. No bearer secrets in JS."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.database.db import get_db_connection

router = APIRouter(prefix='/auth')
COOKIE = 'specguard_session'


def production():
    return os.getenv('SPECGUARD_ENV', 'development') == 'production'


def authentication_required():
    return production() or os.getenv('SPECGUARD_AUTH_REQUIRED') == 'true'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    result = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3,
                            maxmem=128 * 1024 * 1024)
    return salt + ':' + result.hex()


def limited(key, maximum, seconds=60):
    now = int(time.time())
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT started,count FROM request_limits WHERE key=?', (key,)).fetchone()
        if row and now - row['started'] < seconds:
            if row['count'] >= maximum:
                raise HTTPException(429, 'Limit reached; try again later', headers={'Retry-After': str(seconds)})
            conn.execute('UPDATE request_limits SET count=count+1 WHERE key=?', (key,))
        else:
            conn.execute('INSERT OR REPLACE INTO request_limits VALUES (?,?,1)', (key, now))
        conn.execute('DELETE FROM request_limits WHERE started < ?', (now - 86400,))


def session(raw):
    if not raw or len(raw) > 128:
        return None
    with get_db_connection() as conn:
        row = conn.execute('''SELECT users.id,users.username FROM sessions JOIN users
            ON users.id=sessions.user_id WHERE digest=? AND expires_at>?''',
                           (digest(raw), int(time.time()))).fetchone()
    return dict(row) if row else None


class Credentials(BaseModel):
    username: str = Field(pattern=r'^[a-zA-Z0-9_]{3,32}$')
    password: str = Field(min_length=12, max_length=128)


def establish(response, user):
    raw = secrets.token_urlsafe(32)
    with get_db_connection() as conn:
        conn.execute('DELETE FROM sessions WHERE expires_at<?', (int(time.time()),))
        # At most five devices per account, newest sign-ins revoke the oldest.
        conn.execute('''DELETE FROM sessions WHERE user_id=? AND digest NOT IN
            (SELECT digest FROM sessions WHERE user_id=? ORDER BY expires_at DESC LIMIT 4)''',
                     (user['id'], user['id']))
        conn.execute('INSERT INTO sessions VALUES (?,?,?)',
                     (digest(raw), user['id'], int(time.time()) + 8 * 3600))
    response.set_cookie(COOKIE, raw, httponly=True, secure=production(), samesite='strict',
                        max_age=8 * 3600, path='/')
    return {'user': user, 'csrf': digest('csrf:' + raw)}


@router.post('/signup', status_code=201)
def signup(body: Credentials, request: Request, response: Response):
    limited('signup:' + request.client.host, 5, 3600)
    limited('global-signup', 20)
    if os.getenv('SPECGUARD_SIGNUP_ENABLED', 'true') != 'true':
        raise HTTPException(403, 'New account registration is currently closed')
    username = body.username.lower()
    hashed = password_hash(body.password)
    user = {'id': uuid.uuid4().hex, 'username': username}
    recovery = secrets.token_urlsafe(24)
    try:
        with get_db_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT count(*) FROM users').fetchone()[0] >= int(os.getenv('SPECGUARD_MAX_ACCOUNTS', '500')):
                raise HTTPException(503, 'Registration capacity reached; try again later')
            conn.execute('INSERT INTO users (id,username,password_hash,created_at,recovery_hash) VALUES (?,?,?,?,?)',
                         (user['id'], username, hashed, int(time.time()), digest(recovery)))
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'This username is unavailable') from None
    return {**establish(response, user), 'recovery_code': recovery}


class Recover(Credentials):
    recovery_code: str = Field(min_length=24, max_length=128)


@router.post('/recover')
def recover(body: Recover, request: Request, response: Response):
    limited('recover-ip:' + request.client.host, 5, 900)
    limited('recover-user:' + body.username.lower(), 5, 900)
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM users WHERE username=?', (body.username.lower(),)).fetchone()
        if not row or not hmac.compare_digest(row['recovery_hash'] or '', digest(body.recovery_code)):
            raise HTTPException(401, 'Username or recovery code is incorrect')
        replacement = secrets.token_urlsafe(24)
        conn.execute('UPDATE users SET password_hash=?,recovery_hash=? WHERE id=?',
                     (password_hash(body.password), digest(replacement), row['id']))
        conn.execute('DELETE FROM sessions WHERE user_id=?', (row['id'],))
    return {**establish(response, {'id': row['id'], 'username': row['username']}),
            'recovery_code': replacement}


@router.post('/login')
def login(body: Credentials, request: Request, response: Response):
    limited('login:' + request.client.host, 10)
    limited('global-login', 100)
    limited('login-user:' + body.username.lower(), 20, 900)
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM users WHERE username=?', (body.username.lower(),)).fetchone()
    stored = row['password_hash'] if row else '00' * 16 + ':' + '00' * 64
    valid = hmac.compare_digest(password_hash(body.password, stored.split(':')[0]), stored)
    if not row or not valid:
        raise HTTPException(401, 'Username or password is incorrect')
    return establish(response, {'id': row['id'], 'username': row['username']})


@router.get('/session')
def current_session(request: Request):
    raw = request.cookies.get(COOKIE, '')
    user = session(raw)
    if user:
        return {'user': user, 'csrf': digest('csrf:' + raw)}
    if not authentication_required() and not os.getenv('SPECGUARD_API_TOKEN'):
        return {'user': {'id': 'local', 'username': 'Local workspace'}, 'csrf': ''}
    raise HTTPException(401, 'Sign in to continue')


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM sessions WHERE digest=?',
                     (digest(request.cookies.get(COOKIE, '')),))
    response.delete_cookie(COOKIE, path='/', secure=production(), httponly=True, samesite='strict')


@router.delete('/account', status_code=204)
def delete_account(request: Request, response: Response):
    user_id = request.state.owner_id
    if user_id == 'local':
        raise HTTPException(400, 'Local workspace is not an account')
    from backend.api.routes import delete_owned_projects
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM execution_lease WHERE expires_at>?',
                        (int(time.time()),)).fetchone():
            raise HTTPException(409, 'Wait for the active verification before deleting your account')
        delete_owned_projects(conn, user_id)
        conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    response.delete_cookie(COOKIE, path='/', secure=production(), httponly=True, samesite='strict')
