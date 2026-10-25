"""Integrated API + AI + real local runner checks using only trusted demo code."""

import pytest
from fastapi.testclient import TestClient

from backend.database import db
from backend.runner.pytest_runner import PytestRunner
from shared.schemas import GeneratedTest
from specguard_ai.demo_assets import load_demo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'integration.db'))
    monkeypatch.setenv('SPECGUARD_BACKEND_PROVIDER', 'mock')
    db.init_db()
    from backend.api import routes
    from backend.main import app
    from backend.services.verification import VerificationService

    monkeypatch.setattr(routes, 'verification_service', VerificationService(use_docker=False))
    with TestClient(app) as client:
        yield client


def test_two_projects_reverification_and_fix_retest(client):
    fixture = load_demo('add')
    ids = []
    for _ in range(2):
        response = client.post('/projects', json={'specification': fixture['spec'],
                                                 'source_code': fixture['bad_code']})
        assert response.status_code == 200
        project_id = response.json()['project_id']
        ids.append(project_id)
        response = client.post(f'/projects/{project_id}/verify', json={})
        assert response.status_code == 200, response.text
        assert response.json()['failed'] > 0
    project_id = ids[0]
    before = client.get(f'/projects/{project_id}/report').json()['report']
    assert before['fix_suggestions']
    assert client.post(f'/projects/{project_id}/verify', json={}).status_code == 200
    repeated = client.get(f'/projects/{project_id}/report').json()['report']
    assert len(repeated['test_results']) == len(before['test_results'])
    response = client.post(f'/projects/{project_id}/retest', json={'updated_code': fixture['good_code']})
    assert response.status_code == 200, response.text
    assert response.json()['verified']
    after = client.get(f'/projects/{project_id}/report').json()['report']
    assert after['tests'] == before['tests']
    assert after['fix_suggestions'] == []
    assert after['summary']['failed'] == 0
    assert client.get(f'/projects/{project_id}').json()['source_code'] == fixture['good_code']
    assert len(client.get('/projects').json()['projects']) == 2
    assert client.get(f'/projects/{ids[1]}/report').json()['report']['summary']['failed'] > 0
    assert '<html>' in client.get(f'/projects/{project_id}/report?format=html').json()['report']


def test_unknown_project_empty_input_and_demo(client):
    assert client.get('/projects/missing/report').status_code == 404
    assert client.post('/projects', json={'specification': '', 'source_code': ''}).status_code == 422
    assert client.get('/demos/cart').json()['specification'] == load_demo('cart')['spec']
    assert client.get('/demos/unknown').status_code == 404


def test_runner_collection_errors_and_filename_safety():
    runner = PytestRunner(use_docker=False)
    tests = [GeneratedTest(id='../../escape', requirement_id='REQ-001',
                           pytest_code='import nonexistent_specguard_module\n', description='bad import')]
    result = runner.run_tests(tests, 'x = 1', retry_count=0)[0]
    assert result.status == 'error'
    assert result.test_id == '../../escape'


def test_runner_timeouts():
    runner = PytestRunner(use_docker=False)
    test = GeneratedTest(id='TEST-001', requirement_id='REQ-001',
                         pytest_code='from submission import hang\ndef test_hang():\n    assert hang() == 0\n', description='timeout')
    assert runner.run_tests([test], 'def hang():\n    while True: pass\n', timeout_sec=1, retry_count=0)[0].status == 'timeout'


def test_request_cannot_disable_docker(client, monkeypatch):
    from backend.api import routes
    from backend.services.verification import VerificationService

    monkeypatch.setattr(routes, 'verification_service', VerificationService(use_docker=True))
    demo = load_demo('add')
    project_id = client.post('/projects', json={'specification': demo['spec'],
                                               'source_code': demo['bad_code']}).json()['project_id']
    response = client.post(f'/projects/{project_id}/verify', json={'use_docker': False})
    assert response.status_code == 400
