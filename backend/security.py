"""Bounded, local-first HTTP boundary for the verification API."""

import asyncio
import hmac
import ipaddress
import os
from collections import deque
from http.cookies import SimpleCookie
from time import monotonic

from starlette.responses import JSONResponse

from backend.auth import COOKIE, authentication_required, digest, limited, session

DEFAULT_ORIGINS = (
    "http://127.0.0.1:5173,http://localhost:5173,"
    "http://127.0.0.1:5175,http://localhost:5175"
)
MAX_BODY_BYTES = 256 * 1024


def allowed_origins():
    return {origin.strip().rstrip('/') for origin in os.getenv(
        'SPECGUARD_CORS_ORIGINS', DEFAULT_ORIGINS
    ).split(',') if origin.strip() and origin.strip() != '*'}


class SecurityBoundary:
    def __init__(self, app):
        self.app = app
        self.mutations = {}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        origin = headers.get(b'origin', b'').decode('latin1').rstrip('/')
        method = scope['method']

        async def reject(status, message):
            await JSONResponse({'detail': message}, status_code=status)(scope, receive, send)

        if origin and origin not in allowed_origins():
            return await reject(403, 'This browser origin is not permitted')
        if headers.get(b'sec-fetch-site') == b'cross-site' and not origin:
            return await reject(403, 'Cross-site requests are not permitted')
        token = os.getenv('SPECGUARD_API_TOKEN', '')
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get(b'cookie', b'').decode('latin1'))
        except Exception:
            return await reject(400, 'Invalid cookies')
        raw = cookies[COOKIE].value if COOKIE in cookies else ''
        user = session(raw) if raw else None
        scope.setdefault('state', {})['owner_id'] = user['id'] if user else 'local'
        public = scope['path'] in {'/health', '/auth/login', '/auth/signup', '/auth/session', '/auth/recover'}
        client = (scope.get('client') or ('', 0))[0]
        try:
            local = ipaddress.ip_address(client).is_loopback
        except ValueError:
            # Starlette TestClient uses a synthetic peer, never a network address.
            local = client == 'testclient'
        if not local and os.getenv('SPECGUARD_RUNNER', 'docker') == 'local':
            return await reject(403, 'Local execution only accepts loopback clients')
        if authentication_required() and method != 'OPTIONS':
            if not public and not user:
                return await reject(401, 'Sign in to continue')
            if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
                if headers.get(b'x-specguard-client') != b'web':
                    return await reject(403, 'A browser client header is required')
                if user and not hmac.compare_digest(
                    headers.get(b'x-csrf-token', b''), digest('csrf:' + raw).encode()
                ):
                    return await reject(403, 'Session validation failed; sign in again')
        elif method != 'OPTIONS' and not user:
            supplied = headers.get(b'authorization', b'').decode('latin1')
            if token:
                if not hmac.compare_digest(supplied.encode(), f'Bearer {token}'.encode()):
                    return await reject(401, 'Valid API credentials are required')
            elif not local:
                return await reject(403, 'Remote API access requires server authentication')
        if user and method in {'POST', 'PUT', 'PATCH', 'DELETE'} and not hmac.compare_digest(
            headers.get(b'x-csrf-token', b''), digest('csrf:' + raw).encode()
        ):
            return await reject(403, 'Session validation failed; sign in again')
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            if user:
                try:
                    limited('mutation:' + user['id'], 60)
                except Exception as exc:
                    if getattr(exc, 'status_code', None) == 429:
                        return await reject(429, 'Too many requests; try again later')
                    raise
            now = monotonic()
            # Keep the limiter bounded even if the service is configured for remote use.
            if len(self.mutations) >= 1024:
                self.mutations = {key: times for key, times in self.mutations.items()
                                  if times and now - times[-1] < 60}
                if len(self.mutations) >= 1024:
                    return await reject(429, 'API capacity reached; try again later')
            times = self.mutations.setdefault(client, deque())
            while times and now - times[0] >= 60:
                times.popleft()
            if len(times) >= 60:
                return await reject(429, 'Too many requests; try again in a minute')
            times.append(now)
            try:
                declared = int(headers.get(b'content-length', b'0'))
            except ValueError:
                return await reject(400, 'Invalid Content-Length')
            if declared < 0:
                return await reject(400, 'Invalid Content-Length')
            if declared > MAX_BODY_BYTES:
                return await reject(413, 'Request body is too large')
            if headers.get(b'content-encoding', b'identity') not in {b'identity', b''}:
                return await reject(415, 'Compressed request bodies are not supported')
            # Enforce the same limit for streamed/chunked bodies before JSON parsing.
            body = bytearray()
            started = monotonic()
            while True:
                try:
                    message = await asyncio.wait_for(receive(), max(.001, 10 - (monotonic() - started)))
                except TimeoutError:
                    return await reject(408, 'Request body upload timed out')
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    return await reject(413, 'Request body is too large')
                body.extend(chunk)
                if not message.get('more_body', False):
                    break
            sent = False

            async def bounded_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                return await receive()
        else:
            bounded_receive = receive

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = [
                    *message.get('headers', []),
                    (b'x-content-type-options', b'nosniff'),
                    (b'x-frame-options', b'DENY'),
                    (b'referrer-policy', b'no-referrer'),
                    (b'cache-control', b'no-store'),
                    (b'content-security-policy', b"default-src 'none'; frame-ancestors 'none'"),
                ]
            await send(message)
        await self.app(scope, bounded_receive, secure_send)
