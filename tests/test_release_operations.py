"""Operations must fail closed and preserve data during recovery."""
import json
import sqlite3
import subprocess

import pytest
from fastapi import HTTPException

from backend.database import db
from scripts.database import copy_database


def test_backup_restore_and_no_overwrite(tmp_path):
    source, backup, restored = [tmp_path / n for n in ['original.db', 'backup.db', 'restored.db']]
    with sqlite3.connect(source) as conn:
        conn.execute('CREATE TABLE sample (value TEXT)')
        conn.execute('INSERT INTO sample VALUES (?)', ('important test data',))
    copy_database(source, backup)
    copy_database(backup, restored)
    with sqlite3.connect(restored) as conn:
        assert conn.execute('SELECT value FROM sample').fetchone()[0] == 'important test data'
    with pytest.raises(ValueError):
        copy_database(backup, restored)


def test_production_config_fails_closed(monkeypatch):
    from backend.main import validate_config
    monkeypatch.setenv('SPECGUARD_ENV', 'production')
    monkeypatch.setenv('SPECGUARD_RUNNER', 'local')
    with pytest.raises(RuntimeError, match='Docker'):
        validate_config()


def test_hard_job_timeout_marks_run_failed(tmp_path, monkeypatch):
    from backend.services import jobs
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'jobs.db'))
    db.init_db()
    db.ProjectDB.create_project('p', 'spec', 'source')
    with db.get_db_connection() as conn:
        conn.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,NULL,NULL)', ('r', 'p', 'local', 'hash', 'running', 1))
    def timeout(*args, **kwargs):
        assert kwargs['timeout'] == 150
        raise subprocess.TimeoutExpired(args[0], 150)
    monkeypatch.setattr(jobs.subprocess, 'run', timeout)
    with pytest.raises(HTTPException) as exc:
        jobs.bounded_operation('verify', project_id='p')
    assert exc.value.status_code == 502
    with db.get_db_connection() as conn:
        assert conn.execute('SELECT status FROM runs WHERE id=\'r\'').fetchone()[0] == 'failed'


def test_worker_requires_private_credential(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.runner.worker import app
    monkeypatch.setenv('SPECGUARD_WORKER_TOKEN', 'x' * 40)
    with TestClient(app) as client:
        assert client.get('/ready').status_code == 401
        assert client.post('/run', json={}).status_code == 401
        result = client.post('/run', content=b'x' * (513 * 1024), headers={'Authorization': 'Bearer ' + 'x' * 40})
        assert result.status_code == 413


def test_mutation_quotas_are_durable(tmp_path, monkeypatch):
    from backend.auth import limited
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'limits.db'))
    db.init_db()
    limited('quota-test', 1)
    with pytest.raises(HTTPException) as exc:
        limited('quota-test', 1)
    assert exc.value.status_code == 429


def test_no_expected_answers_are_sent_to_execution_process(tmp_path):
    from backend.runner.cases import extract
    cases = extract('from submission import f\ndef test_f():\n    assert f(1) == 98765\n')
    inputs = json.dumps([{'function': c.function, 'args': c.args, 'kwargs': c.kwargs} for c in cases])
    assert '98765' not in inputs
