from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime,timezone
from typing import Optional, List
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class ProjectBase(SQLModel):
    name: str
    settings: Optional[dict] = {}
    ai_prompt: Optional[str] = None


class Project(ProjectBase, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    jurisdictions: List["Jurisdiction"] = Relationship(back_populates="project")


from app.api.modules.v1.jurisdictions.models.jurisdiction_models import Jurisdiction
