"""
FastAPI route handlers.
"""

import logging
import os
import subprocess
import time
import uuid
from contextlib import contextmanager
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, StringConstraints

from backend.auth import limited, production
from backend.database.db import ProjectDB, get_db_connection, init_db
from backend.reports.generator import ReportGenerator
from backend.services.verification import VerificationService
from backend.ai.provider import ProviderError

router = APIRouter()
logger = logging.getLogger(__name__)
execution_slot = BoundedSemaphore(1)


@contextmanager
def execution_capacity(owner_id='local'):
    if not execution_slot.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A verification is already running")
    try:
        lease = uuid.uuid4().hex
        with get_db_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM execution_lease WHERE expires_at<?', (int(time.time()),))
            if conn.execute('SELECT 1 FROM execution_lease').fetchone():
                raise HTTPException(409, 'A verification is already running; try again later')
            conn.execute('INSERT INTO execution_lease VALUES (1,?,?)',
                         (lease, int(time.time()) + 180))
        try:
            if owner_id != 'local':
                limited('daily-runs:' + owner_id, int(os.getenv('SPECGUARD_DAILY_RUNS', '20')), 86400)
                limited('global-daily-runs', int(os.getenv('SPECGUARD_GLOBAL_DAILY_RUNS', '100')), 86400)
            yield
        finally:
            with get_db_connection() as conn:
                conn.execute('DELETE FROM execution_lease WHERE token=?', (lease,))
    finally:
        execution_slot.release()

# Initialize database on first import
init_db()

# Initialize verification service
verification_service = VerificationService(use_docker=os.getenv("SPECGUARD_RUNNER", "docker") != "local")


# Request/Response Models
ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RenameProjectRequest(BaseModel):
    name: ProjectName


class CreateProjectRequest(BaseModel):
    name: ProjectName = 'Untitled project'
    specification: str = Field(min_length=1, max_length=60000)
    source_code: str = Field(min_length=1, max_length=60000)


class VerifyRequest(BaseModel):
    use_docker: bool = True


class RetestRequest(BaseModel):
    updated_code: str = Field(min_length=1, max_length=60000)


def owned(project_id, request):
    project = ProjectDB.get_project(project_id)
    if not project or project['owner_id'] != request.state.owner_id:
        raise HTTPException(404, 'Project not found')
    return project


def delete_owned_projects(conn, owner_id, project_id=None):
    ids = [r[0] for r in conn.execute('SELECT id FROM projects WHERE owner_id=?', (owner_id,))
           if project_id is None or r[0] == project_id]
    for pid in ids:
        for table in ('test_results', 'static_findings', 'fix_suggestions', 'generated_tests',
                      'requirements', 'verification_snapshots', 'runs'):
            conn.execute(f'DELETE FROM {table} WHERE project_id=?', (pid,))
        conn.execute('DELETE FROM projects WHERE id=?', (pid,))


@router.post("/projects")
def create_project(request: CreateProjectRequest, http: Request):
    """
    Create a new verification project.

    Args:
        request: Contains specification and source_code

    Returns:
        Project ID
    """
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    ProjectDB.create_project(
        project_id=project_id,
        specification=request.specification,
        source_code=request.source_code,
        owner_id=http.state.owner_id,
        name=request.name,
    )
    return {"project_id": project_id}


@router.post("/projects/{project_id}/verify")
def verify_project(project_id: str, http: Request, request: VerifyRequest = None):
    """
    Run verification on a project.

    Args:
        project_id: ID of the project
        request: Optional parameters (use_docker)

    Returns:
        Verification results summary
    """
    if request is None:
        request = VerifyRequest()

    project = owned(project_id, http)

    try:
        with execution_capacity(http.state.owner_id):
            from backend.services.jobs import bounded_operation
            operation = (lambda **kw: bounded_operation('verify', **kw)) if production() else verification_service.verify
            results = operation(
                project_id=project_id,
                specification=project["specification"],
                source_code=project["source_code"],
                use_docker=request.use_docker,
            )
        http.state.run_id = results.get('run_id')
        return results
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        logger.exception("Verification API operation failed")
        raise HTTPException(status_code=500, detail="The operation failed; check the server logs") from None


@router.get("/projects/{project_id}/report")
def get_report(project_id: str, http: Request, format: str = "json"):
    """
    Get the verification report.

    Args:
        project_id: ID of the project
        format: 'json' or 'html'

    Returns:
        Report in the requested format
    """
    owned(project_id, http)

    try:
        if format == "html":
            html_report = ReportGenerator.generate_html_report(project_id)
            return {"report": html_report, "format": "html"}
        else:  # Default to JSON
            json_report = ReportGenerator.generate_json_report(project_id)
            return {"report": json_report, "format": "json"}
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        logger.exception("Verification API operation failed")
        raise HTTPException(status_code=500, detail="The operation failed; check the server logs") from None


@router.post("/projects/{project_id}/retest")
def retest_project(project_id: str, request: RetestRequest, http: Request):
    """
    Re-run verification after code changes.

    Args:
        project_id: ID of the project
        request: Contains updated_code

    Returns:
        New verification results
    """
    owned(project_id, http)

    try:
        with execution_capacity(http.state.owner_id):
            from backend.services.jobs import bounded_operation
            operation = (lambda **kw: bounded_operation('retest', **kw)) if production() else verification_service.retest
            results = operation(
                project_id=project_id,
                updated_code=request.updated_code,
            )
        http.state.run_id = results.get('run_id')
        return results
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        logger.exception("Verification API operation failed")
        raise HTTPException(status_code=500, detail="The operation failed; check the server logs") from None


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/projects")
def list_projects(http: Request, limit: int = Query(100, ge=1, le=100),
                  offset: int = Query(0, ge=0)):
    with get_db_connection() as conn:
        rows = conn.execute('''SELECT id, name, created_at, updated_at FROM projects WHERE owner_id=?
            ORDER BY updated_at DESC,id LIMIT ? OFFSET ?''',
                            (http.state.owner_id, limit, offset)).fetchall()
    return {"projects": [dict(row) for row in rows]}


@router.get("/projects/{project_id}")
def get_project(project_id: str, http: Request):
    return owned(project_id, http)


@router.patch('/projects/{project_id}')
def rename_project(project_id: str, request: RenameProjectRequest, http: Request):
    """Rename an owned project without changing code or verification evidence."""
    owned(project_id, http)
    with get_db_connection() as conn:
        result = conn.execute(
            'UPDATE projects SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND owner_id=?',
            (request.name, project_id, http.state.owner_id),
        )
        if not result.rowcount:
            raise HTTPException(404, 'Project not found')
    return ProjectDB.get_project(project_id)


@router.delete('/projects/{project_id}', status_code=204)
def delete_project(project_id: str, http: Request):
    owned(project_id, http)
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM execution_lease WHERE expires_at>?',
                        (int(time.time()),)).fetchone():
            raise HTTPException(409, 'Wait for the active verification before deleting data')
        delete_owned_projects(conn, http.state.owner_id, project_id)


@router.get('/ready')
def readiness():
    try:
        with get_db_connection() as conn:
            conn.execute('SELECT version FROM schema_version').fetchone()
        if hasattr(verification_service.runner, 'ready'):
            verification_service.runner.ready()
        elif verification_service.runner.use_docker:
            subprocess.run(['docker', 'image', 'inspect', verification_service.runner.docker_image],
                           capture_output=True, check=True, timeout=5)
    except Exception:
        raise HTTPException(503, 'Verification service is not ready') from None
    return {'status': 'ready'}


@router.get('/capabilities')
def capabilities():
    return {'provider': os.getenv('SPECGUARD_BACKEND_PROVIDER', 'mock'),
            'runner': 'docker' if verification_service.runner.use_docker else 'trusted-local',
            'supported': 'Synchronous top-level Python functions with JSON inputs and outputs',
            'evidence': 'Finite generated cases; not a proof of correctness or hostile-code attestation',
            'limits': {'projects': 20, 'requirements': 8, 'run_seconds': 140,
                       'daily_runs': int(os.getenv('SPECGUARD_DAILY_RUNS', '20'))}}


@router.get("/demos/{name}")
def get_demo(name: str):
    from backend.ai.demo_assets import load_demo
    if name not in {"add", "divide", "cart"}:
        raise HTTPException(status_code=404, detail="Unknown demo")
    fixture = load_demo(name)
    return {"specification": fixture["spec"], "source_code": fixture["bad_code"]}
