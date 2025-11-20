from datetime import datetime, timezone
from typing import TYPE_CHECKING, Column, Optional
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.api.modules.v1.projects.models.project import Project
from app.api.modules.v1.users.models.users_model import User

if TYPE_CHECKING:
    from app.api.modules.v1.projects.models.project import Project
    from app.api.modules.v1.users.models.users_model import User


class ProjectUser(SQLModel, table=True):
    """
    Table linking projects to users.
    """

    __tablename__ = "project_users"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)

    project_id: UUID = Field(foreign_key="projects.id", primary_key=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    project: Optional[Project] = Relationship(back_populates="project_users")
    user: Optional["User"] = Relationship(back_populates="project_users")
