from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.db.database import get_session
from app.api.modules.v1.projects.models.project import Project
from app.api.modules.v1.jurisdictions.schemas.jurisdiction import (
    JurisdictionCreate, JurisdictionRead
)
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import (
    create_jurisdiction
)

router = APIRouter(prefix="/projects/{project_id}/jurisdictions", tags=["Jurisdictions"])


@router.post("", response_model=JurisdictionRead)
def create_jurisdiction_endpoint(
    project_id: str,
    data: JurisdictionCreate,
    session: Session = Depends(get_session)
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    jurisdiction = create_jurisdiction(session, project_id, data)
    return jurisdiction
