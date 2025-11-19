from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.db.database import get_session
from app.api.modules.v1.projects.schemas.projects_schema import ProjectCreate, ProjectRead
from app.api.modules.v1.projects.service.project_service import create_project

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectRead)
def create_project_endpoint(
    data: ProjectCreate,
    session: Session = Depends(get_session)
):
    project = create_project(session, data)
    return project
