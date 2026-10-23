"""
FastAPI route handlers.
"""

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database.db import ProjectDB, init_db
from backend.services.verification import VerificationService
from backend.reports.generator import ReportGenerator

router = APIRouter()

# Initialize database on first import
init_db()

# Initialize verification service
verification_service = VerificationService(use_docker=False)


# Request/Response Models
class CreateProjectRequest(BaseModel):
    specification: str
    source_code: str


class VerifyRequest(BaseModel):
    use_docker: bool = False


class RetestRequest(BaseModel):
    updated_code: str


@router.post("/projects")
def create_project(request: CreateProjectRequest):
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
    )
    return {"project_id": project_id}


@router.post("/projects/{project_id}/verify")
def verify_project(project_id: str, request: VerifyRequest = None):
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

    project = ProjectDB.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        results = verification_service.verify(
            project_id=project_id,
            specification=project["specification"],
            source_code=project["source_code"],
            use_docker=request.use_docker,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/report")
def get_report(project_id: str, format: str = "json"):
    """
    Get the verification report.
    
    Args:
        project_id: ID of the project
        format: 'json' or 'html'
    
    Returns:
        Report in the requested format
    """
    project = ProjectDB.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        if format == "html":
            html_report = ReportGenerator.generate_html_report(project_id)
            return {"report": html_report, "format": "html"}
        else:  # Default to JSON
            json_report = ReportGenerator.generate_json_report(project_id)
            return {"report": json_report, "format": "json"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/retest")
def retest_project(project_id: str, request: RetestRequest):
    """
    Re-run verification after code changes.
    
    Args:
        project_id: ID of the project
        request: Contains updated_code
    
    Returns:
        New verification results
    """
    project = ProjectDB.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        results = verification_service.retest(
            project_id=project_id,
            updated_code=request.updated_code,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
