"""Platform integration with trusted, persisted AI preparations and runner results."""

import ast
import hashlib
import json
import logging
import os
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from backend.database.db import ProjectDB, get_db_connection
from backend.runner.pytest_runner import PytestRunner
from backend.ai.api import analyze_code
from backend.ai.budget import CURRENT, run_budget
from backend.ai.provider import using_provider
from backend.ai.workflow import Preparation, assemble_preparation, finish, prepare

_LOCK = RLock()


def load_report(project_id: str) -> dict:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT data FROM verification_snapshots WHERE project_id = ?", (project_id,)
        ).fetchone()
    if not row:
        if not ProjectDB.get_project(project_id):
            raise ValueError("Project not found")
        report = {"project_id": project_id, "status": "not_run", "summary": {},
                "generated_at": None,
                "requirements": [], "tests": [], "test_results": [],
                "static_findings": [], "fix_suggestions": [], "requirement_states": []}
    else:
        report = json.loads(row[0])
    with get_db_connection() as conn:
        latest = conn.execute('SELECT id,status,error FROM runs WHERE project_id=? '
                              'ORDER BY created_at DESC,rowid DESC LIMIT 1', (project_id,)).fetchone()
    if latest and latest['status'] != 'complete':
        report['previous_summary'] = report['summary']
        report['summary'] = {**report['summary'], 'verified': False}
        report['status'] = latest['status']
        report['run_id'] = latest['id']
        report['error'] = latest['error']
    return report


def supported_source(code):
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError):
        raise ValueError('Submit valid Python source') from None
    if (not any(isinstance(n, ast.FunctionDef) for n in tree.body)
            or any(isinstance(n, (ast.ClassDef, ast.AsyncFunctionDef)) for n in tree.body)):
        raise ValueError('Supported inputs are synchronous top-level functions, not classes or async APIs')


@contextmanager
def tracked_run(project_id, source):
    run_id = uuid.uuid4().hex
    project = ProjectDB.get_project(project_id)
    with get_db_connection() as conn:
        conn.execute('UPDATE runs SET status=\'interrupted\', error=\'Previous worker stopped\' '
                     'WHERE status=\'running\' AND created_at<?', (int(time.time()) - 180,))
        conn.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,NULL,NULL)',
                     (run_id, project_id, project['owner_id'], hashlib.sha256(source.encode()).hexdigest(),
                      'running', int(time.time())))
    started = time.monotonic()
    try:
        with run_budget() as budget:
            yield run_id, budget
    except Exception:
        with get_db_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('UPDATE runs SET status=\'failed\',error=? WHERE id=?',
                         ('Run failed; previous evidence is not current. Retry or contact support.', run_id))
        logging.getLogger(__name__).exception('verification_failed run_id=%s', run_id)
        raise
    finally:
        logging.getLogger(__name__).info('verification_finished run_id=%s duration_ms=%s',
                                         run_id, int((time.monotonic() - started) * 1000))


class VerificationService:
    def __init__(self, use_docker: bool = True):
        if os.getenv('SPECGUARD_WORKER_URL'):
            from backend.runner.remote import RemoteRunner
            self.runner = RemoteRunner()
        else:
            self.runner = PytestRunner(use_docker=use_docker)

    def _complete(self, project_id, prepared, source_code, run_id):
        from datetime import UTC, datetime

        budget = CURRENT.get()
        results = self.runner.run_tests(prepared.tests, source_code,
                                        deadline=budget.deadline if budget else None) if prepared.tests else []
        verification = finish(prepared, source_code, results,
                              bundle_sha256=prepared.bundle_sha256)
        counts = Counter(result.status for result in results)
        summary = {"total_requirements": len(prepared.requirements),
                   "total_tests": len(prepared.tests), "total_results": len(results),
                   "passed": counts['passed'], "failed": counts['failed'],
                   "errors": counts['error'], "timeouts": counts['timeout'],
                   "flaky": counts['flaky'], "verified": verification.verified}
        report = {"project_id": project_id, "status": "complete",
                  "run_id": run_id,
                  "provenance": {'app_version': '0.2.0', 'runner': 'external-comparison-v1',
                                 'execution_mode': ('private-worker' if os.getenv('SPECGUARD_WORKER_URL') else
                                                    'docker' if self.runner.use_docker else 'trusted-local'),
                                 'prompt_sha256': hashlib.sha256(b''.join(
                                     p.read_bytes() for p in sorted((Path(__file__).resolve().parents[2] / 'backend/ai/prompts').glob('*.txt')))).hexdigest(),
                                 'provider': prepared.provider,
                                 'model': os.getenv(prepared.provider.upper() + '_MODEL', 'mock'),
                                 'code_model': os.getenv('NVIDIA_CODE_MODEL') if prepared.provider == 'nvidia' else None,
                                 'source_sha256': prepared.source_sha256,
                                 'bundle_sha256': prepared.bundle_sha256},
                  "generated_at": datetime.now(UTC).isoformat(), "summary": summary,
                  "preparation": prepared.model_dump(),
                  "requirements": [r.model_dump() for r in prepared.requirements],
                  "tests": [t.model_dump() for t in prepared.tests],
                  "test_results": [r.model_dump() for r in verification.results],
                  "static_findings": [f.model_dump() for f in prepared.static_findings],
                  "fix_suggestions": [f.model_dump() for f in verification.fixes],
                  "requirement_states": [s.model_dump() for s in verification.requirement_states]}
        with get_db_connection() as conn:
            # Cap historical evidence per project without evicting active work.
            conn.execute('DELETE FROM runs WHERE project_id=? AND id NOT IN '
                         '(SELECT id FROM runs WHERE project_id=? ORDER BY created_at DESC,rowid DESC LIMIT 10)',
                         (project_id, project_id))
            size = len(json.dumps(report).encode())
            stored = conn.execute('SELECT COALESCE(sum(length(CAST(report AS BLOB))),0) FROM runs').fetchone()[0]
            owned_size = conn.execute('SELECT COALESCE(sum(length(CAST(report AS BLOB))),0) FROM runs WHERE owner_id=?',
                                      (ProjectDB.get_project(project_id)['owner_id'],)).fetchone()[0]
            if stored + size > 500 * 1024 * 1024 or owned_size + size > 50 * 1024 * 1024:
                raise ValueError('Evidence storage quota reached; delete old projects before retrying')
            conn.execute('UPDATE runs SET status=\'complete\',report=? WHERE id=?',
                         (json.dumps(report), run_id))
            conn.execute("INSERT OR REPLACE INTO verification_snapshots VALUES (?, ?)",
                         (project_id, json.dumps(report)))
            conn.execute("UPDATE projects SET source_code=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (source_code, project_id))
        return {"project_id": project_id, "run_id": run_id, **summary}

    def verify(self, project_id, specification, source_code, use_docker=True):
        # Local execution is a server-only development choice, never a remote request toggle.
        if not use_docker and self.runner.use_docker:
            raise ValueError("Local execution must be enabled by the server operator")
        supported_source(source_code)
        with _LOCK, tracked_run(project_id, source_code) as (run_id, _budget):
            if hasattr(self.runner, 'ready'):
                self.runner.ready()
            prepared = prepare(specification, source_code,
                               provider=os.getenv("SPECGUARD_BACKEND_PROVIDER", "mock"))
            return self._complete(project_id, prepared, source_code, run_id)

    def retest(self, project_id, updated_code):
        supported_source(updated_code)
        with _LOCK:
            report = load_report(project_id)
            if "preparation" not in report:
                raise ValueError("Verify this project before retesting")
            previous = Preparation.model_validate(report['preparation'])
            with tracked_run(project_id, updated_code) as (run_id, _budget):
                if hasattr(self.runner, 'ready'):
                    self.runner.ready()
                with using_provider(previous.provider):
                    prepared = assemble_preparation(updated_code, previous.provider,
                                                    previous.requirements, previous.tests,
                                                    analyze_code(updated_code, previous.requirements))
                return self._complete(project_id, prepared, updated_code, run_id)
