"""Regression checks for the HTTP boundary and bounded execution output."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security import MAX_BODY_BYTES, SecurityBoundary


@pytest.fixture
def guarded(monkeypatch):
    monkeypatch.delenv('SPECGUARD_API_TOKEN', raising=False)
    monkeypatch.setenv('SPECGUARD_RUNNER', 'docker')
    app = FastAPI()
    app.add_middleware(SecurityBoundary)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/data')
    def data(payload: dict):
        return payload

    return app


def test_untrusted_origin_is_rejected_even_for_simple_requests(guarded):
    with TestClient(guarded) as client:
        assert client.get('/health', headers={'Origin': 'https://attacker.invalid'}).status_code == 403
        assert client.post('/data', content='{}', headers={
            'Origin': 'null', 'Content-Type': 'text/plain'
        }).status_code == 403
        assert client.get('/health', headers={'Origin': 'http://127.0.0.1:5175'}).status_code == 200


def test_remote_access_requires_authentication(guarded, monkeypatch):
    with TestClient(guarded, client=('203.0.113.10', 12345)) as client:
        assert client.get('/health').status_code == 403
        monkeypatch.setenv('SPECGUARD_API_TOKEN', 'unit-test-api-token')
        assert client.get('/health').status_code == 401
        assert client.get('/health', headers={'Authorization': 'Bearer wrong'}).status_code == 401
        headers = {'Authorization': 'Bearer unit-test-api-token'}
        assert client.get('/health', headers=headers).status_code == 200
        monkeypatch.setenv('SPECGUARD_RUNNER', 'local')
        assert client.get('/health', headers=headers).status_code == 403


def test_chunked_and_declared_oversized_bodies_are_bounded(guarded):
    with TestClient(guarded) as client:
        assert client.post('/data', content=b'x', headers={
            'Content-Length': str(MAX_BODY_BYTES + 1)
        }).status_code == 413
        chunks = (b'x' * 65536 for _ in range(5))
        assert client.post('/data', content=chunks).status_code == 413
        assert client.post('/data', json={'ok': True}).status_code == 200


def test_mutation_rate_limit_and_security_headers(guarded):
    with TestClient(guarded) as client:
        response = client.get('/health')
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-frame-options'] == 'DENY'
        for _ in range(60):
            assert client.post('/data', json={}).status_code == 200
        assert client.post('/data', json={}).status_code == 429


def test_host_header_rebinding_rejected():
    from backend.main import app
    with TestClient(app) as client:
        assert client.get('/health', headers={'Host': 'attacker.invalid'}).status_code == 400


def test_runner_output_limit():
    from backend.runner.pytest_runner import PytestRunner
    from shared.schemas import GeneratedTest
    test = GeneratedTest(id='TEST-001', requirement_id='REQ-001',
                         description='Bound noisy collection output',
                         pytest_code='from submission import noisy\ndef test_noisy():\n    assert noisy() == 0\n')
    runner = PytestRunner(use_docker=False)
    result = runner.run_tests([test], "import sys\ndef noisy():\n    sys.stderr.write('x' * 1500000)\n    return 0\n", timeout_sec=10, retry_count=0)[0]
    assert result.status == 'error'
    assert result.output == 'Test exceeded the 1 MB output limit'

def test_api_errors_are_redacted_and_busy_requests_rejected(tmp_path, monkeypatch):
    from backend.api import routes
    from backend.database import db
    from backend.main import app

    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'safe-errors.db'))
    monkeypatch.delenv('SPECGUARD_API_TOKEN', raising=False)
    db.init_db()

    def fail(**kwargs):
        raise RuntimeError('private-internal-value-must-not-leak')

    monkeypatch.setattr(routes.verification_service, 'verify', fail)
    with TestClient(app) as client:
        project = client.post('/projects', json={
            'specification': 'Add two numbers', 'source_code': 'def add(a,b): return a+b'
        }).json()['project_id']
        response = client.post(f'/projects/{project}/verify', json={})
        assert response.status_code == 500
        assert 'private-internal-value' not in response.text
        with routes.execution_capacity():
            response = client.post(f'/projects/{project}/verify', json={})
            assert response.status_code == 409
