from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_user_model import ProjectUser


class Project(SQLModel, table=True):
    """
    Main Project table - represents a high-level container for monitoring.
    """
    __tablename__ = "projects"
 

    id: UUID = Field(default=uuid4, primary_key=True, index=True)
    org_id: UUID = Field(
        foreign_key="organizations.id",
        index=True,
        description="Organization that owns this project",
    )
    title: str = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    master_prompt: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="High-level AI prompt for the entire project",
    ) 
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization: Optional["Organization"] = Relationship(back_populates="projects")

    project_users: List["ProjectUser"] = Relationship(back_populates="projects")