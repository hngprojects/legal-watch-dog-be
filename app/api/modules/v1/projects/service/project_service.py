from sqlmodel import Session
from app.api.modules.v1.projects.models.projects_models import Project
from app.api.modules.v1.projects.schemas.projects_schema import ProjectCreate


def create_project(session: Session, data: ProjectCreate) -> Project:
    project = Project(**data.dict())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
