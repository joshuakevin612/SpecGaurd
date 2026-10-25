"""Release gates for identity, evidence integrity, budgets and recovery."""
import time

import pytest
from fastapi.testclient import TestClient

from backend.database import db
from backend.runner.pytest_runner import PytestRunner
from shared.schemas import GeneratedTest


@pytest.fixture
def public_app(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'accounts.db'))
    db.init_db()
    monkeypatch.setenv('SPECGUARD_ENV', 'production')
    monkeypatch.setenv('SPECGUARD_RUNNER', 'docker')
    monkeypatch.setenv('SPECGUARD_BACKEND_PROVIDER', 'nvidia')
    monkeypatch.setenv('NVIDIA_API_KEY', 'synthetic-release-test-key')
    monkeypatch.setenv('NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1')
    monkeypatch.setenv('NVIDIA_MODEL', 'synthetic-model')
    monkeypatch.setenv('SPECGUARD_ALLOWED_HOSTS', 'testserver')
    monkeypatch.setenv('SPECGUARD_CORS_ORIGINS', 'https://testserver')
    monkeypatch.setenv('SPECGUARD_DB', str(tmp_path / 'accounts.db'))
    monkeypatch.setenv('SPECGUARD_WORKER_URL', 'http://127.0.0.1:8001')
    monkeypatch.setenv('SPECGUARD_WORKER_TOKEN', 'x' * 40)
    monkeypatch.delenv('SPECGUARD_API_TOKEN', raising=False)
    from backend.main import app
    return app


def register(client, name):
    client.headers['X-SpecGuard-Client'] = 'web'
    response = client.post('/auth/signup', json={'username': name, 'password': 'a-long-test-password'})
    assert response.status_code == 201, response.text
    client.headers['X-CSRF-Token'] = response.json()['csrf']
    return response


def test_public_accounts_ownership_csrf_and_deletion(public_app):
    with TestClient(public_app, base_url='https://testserver') as alice, \
            TestClient(public_app, base_url='https://testserver') as bob:
        # Loopback and proxy-like clients never bypass production auth.
        assert alice.get('/projects').status_code == 401
        response = register(alice, 'alice')
        cookie = response.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
        pid = alice.post('/projects', json={'specification': 'Add', 'source_code': 'def add(a,b): return a+b'}).json()['project_id']
        register(bob, 'bob')
        assert bob.get('/projects').json()['projects'] == []
        for suffix in ['', '/report']:
            assert bob.get('/projects/' + pid + suffix).status_code == 404
        assert bob.post(f'/projects/{pid}/verify', json={}).status_code == 404
        assert bob.post(f'/projects/{pid}/retest', json={'updated_code': 'x'}).status_code == 404
        assert bob.delete('/projects/' + pid).status_code == 404
        csrf = alice.headers.pop('X-CSRF-Token')
        assert alice.delete('/projects/' + pid).status_code == 403
        alice.headers['X-CSRF-Token'] = csrf
        assert alice.delete('/projects/' + pid).status_code == 204
        assert alice.get('/projects/' + pid).status_code == 404
        assert alice.delete('/auth/account').status_code == 204
        assert alice.get('/projects').status_code == 401
        assert bob.get('/projects').status_code == 200


def test_recovery_rotates_code_and_revokes_sessions(public_app):
    with TestClient(public_app, base_url='https://testserver') as alice, \
            TestClient(public_app, base_url='https://testserver') as recovery:
        old = register(alice, 'alice').json()['recovery_code']
        recovery.headers['X-SpecGuard-Client'] = 'web'
        response = recovery.post('/auth/recover', json={'username': 'alice',
            'password': 'my-new-long-password', 'recovery_code': old})
        assert response.status_code == 200
        assert response.json()['recovery_code'] != old
        assert alice.get('/projects').status_code == 401
        # The new session must not permit a mutation without its CSRF value.
        assert recovery.post('/auth/logout').status_code == 403
        recovery.headers['X-CSRF-Token'] = response.json()['csrf']
        assert recovery.post('/auth/logout').status_code == 204
        assert recovery.post('/auth/recover', json={'username': 'alice',
            'password': 'my-new-long-password', 'recovery_code': old}).status_code == 401


def test_login_expiry_and_password_hashes(public_app):
    with TestClient(public_app, base_url='https://testserver') as client:
        register(client, 'alice')
        assert client.post('/auth/logout').status_code == 204
        assert client.post('/auth/login', json={'username': 'alice', 'password': 'incorrect-long-pass'}).status_code == 401
        response = client.post('/auth/login', json={'username': 'alice', 'password': 'a-long-test-password'})
        assert response.status_code == 200
        with db.get_db_connection() as conn:
            assert 'a-long-test-password' not in conn.execute('SELECT password_hash FROM users').fetchone()[0]
            conn.execute('UPDATE sessions SET expires_at=?', (int(time.time()) - 1,))
        assert client.get('/projects').status_code == 401


@pytest.mark.parametrize('source', [
    'import os\nos._exit(0)\ndef add(a,b): return 0',
    'import sys\nsys.exit(0)\ndef add(a,b): return 0',
    'import pytest\npytest.skip("skip", allow_module_level=True)\ndef add(a,b): return 0',
    'import os\nos.write(1,b"[]")\nos._exit(0)\ndef add(a,b): return 0',
])
def test_early_exit_never_passes(source):
    test = GeneratedTest(id='TEST-001', requirement_id='REQ-001', description='Addition',
                         pytest_code='from submission import add\ndef test_add():\n    assert add(2,2) == 4\n')
    result = PytestRunner(use_docker=False).run_tests([test], source, retry_count=0)[0]
    assert result.status == 'error'


def test_budget_rejects_unbounded_calls():
    from specguard_ai.budget import run_budget
    from specguard_ai.provider import ProviderError
    with run_budget() as budget:
        for _ in range(10):
            budget.reserve(1, 1)
        with pytest.raises(ProviderError):
            budget.reserve(1, 1)


def test_failed_rerun_invalidates_previous_success(tmp_path, monkeypatch):
    from backend.services import verification as service
    from specguard_ai.demo_assets import load_demo
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'runs.db'))
    monkeypatch.setenv('SPECGUARD_BACKEND_PROVIDER', 'mock')
    db.init_db()
    demo = load_demo('add')
    db.ProjectDB.create_project('p', demo['spec'], demo['good_code'])
    verifier = service.VerificationService(use_docker=False)
    assert verifier.verify('p', demo['spec'], demo['good_code'])['verified']
    def fail(*args, **kwargs):
        raise ValueError('synthetic failure')
    monkeypatch.setattr(service, 'prepare', fail)
    with pytest.raises(ValueError):
        verifier.verify('p', demo['spec'], demo['good_code'])
    report = service.load_report('p')
    assert report['status'] == 'failed' and not report['summary']['verified']
    assert report['previous_summary']['verified']


def test_worker_failure_prevents_paid_preparation(tmp_path, monkeypatch):
    from backend.services import verification as service
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'worker-down.db'))
    db.init_db()
    db.ProjectDB.create_project('p', 'spec', 'def f(): return 1')
    verifier = service.VerificationService(use_docker=False)
    def unavailable():
        raise RuntimeError('worker down')
    verifier.runner.ready = unavailable
    def forbidden(*args, **kwargs):
        raise AssertionError('Provider must not be called while worker is unavailable')
    monkeypatch.setattr(service, 'prepare', forbidden)
    with pytest.raises(RuntimeError, match='worker down'):
        verifier.verify('p', 'spec', 'def f(): return 1')
    assert service.load_report('p')['status'] == 'failed'


def test_worker_url_cannot_send_credentials_to_external_host(public_app, monkeypatch):
    from backend.main import validate_config
    monkeypatch.setenv('SPECGUARD_WORKER_URL', 'http://127.0.0.1:8001@attacker.invalid')
    with pytest.raises(RuntimeError, match='private execution worker'):
        validate_config()


def test_project_names_persist_validate_and_require_owner_and_csrf(public_app):
    with TestClient(public_app, base_url='https://testserver') as alice, \
            TestClient(public_app, base_url='https://testserver') as bob:
        register(alice, 'alice_names')
        created = alice.post('/projects', json={
            'name': '  Cart validation  ', 'specification': 'Add',
            'source_code': 'def add(a,b): return a+b',
        })
        assert created.status_code == 200, created.text
        pid = created.json()['project_id']
        original = alice.get(f'/projects/{pid}').json()
        assert original['name'] == 'Cart validation'
        assert alice.get('/projects').json()['projects'][0]['name'] == 'Cart validation'
        register(bob, 'bob_names')
        assert bob.patch(f'/projects/{pid}', json={'name': 'Not yours'}).status_code == 404
        csrf = alice.headers.pop('X-CSRF-Token')
        assert alice.patch(f'/projects/{pid}', json={'name': 'Blocked'}).status_code == 403
        alice.headers['X-CSRF-Token'] = csrf
        for invalid in ['', '   ', 'x' * 101, None]:
            assert alice.patch(f'/projects/{pid}', json={'name': invalid}).status_code == 422
        renamed = alice.patch(f'/projects/{pid}', json={'name': '  Checkout & refunds  '})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()['name'] == 'Checkout & refunds'
        for field in ['id', 'source_code', 'specification', 'created_at', 'owner_id']:
            assert renamed.json()[field] == original[field]
        assert alice.get('/projects').json()['projects'][0]['name'] == 'Checkout & refunds'
        assert alice.get(f'/projects/{pid}').json()['name'] == 'Checkout & refunds'
        assert alice.patch('/projects/missing', json={'name': 'Missing'}).status_code == 404
        unnamed = alice.post('/projects', json={'specification': 'spec', 'source_code': 'pass'}).json()['project_id']
        assert alice.get(f'/projects/{unnamed}').json()['name'] == 'Untitled project'
        assert alice.post('/projects', json={'name': ' ', 'specification': 'spec', 'source_code': 'pass'}).status_code == 422


def test_project_name_migration_preserves_existing_projects(tmp_path, monkeypatch):
    import sqlite3
    legacy = tmp_path / 'legacy.db'
    with sqlite3.connect(legacy) as conn:
        conn.execute('''CREATE TABLE projects (
            id TEXT PRIMARY KEY, specification TEXT NOT NULL, source_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.execute("INSERT INTO projects (id,specification,source_code) VALUES ('old','legacy spec','legacy source')")
    monkeypatch.setattr(db, 'DB_PATH', str(legacy))
    db.init_db()
    db.init_db()  # Migration is safe on subsequent starts.
    project = db.ProjectDB.get_project('old')
    assert project['name'] == 'Untitled project'
    assert project['specification'] == 'legacy spec'
    assert project['source_code'] == 'legacy source'
