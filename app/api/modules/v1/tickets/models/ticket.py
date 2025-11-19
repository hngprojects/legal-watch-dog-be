from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship
import uuid

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models.users_model import User
    from app.api.modules.v1.projects.models.project import Project


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    organization_id: uuid.UUID = Field(
        foreign_key="organizations.id", nullable=False, index=True
    )

    project_id: uuid.UUID = Field(foreign_key="projects.id", nullable=False, index=True)

    created_by: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)

    assigned_to: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id", index=True
    )

    title: str = Field(max_length=255, nullable=False, index=True)

    description: Optional[str] = Field(default=None)

    status: str = Field(
        default="open", max_length=20, nullable=False, index=True
    )  # open, in_progress, resolved, closed

    priority: str = Field(
        default="medium", max_length=20, nullable=False, index=True
    )  # low, medium, high, critical

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization: "Organization" = Relationship(back_populates="tickets")
    project: "Project" = Relationship(back_populates="tickets")
    creator: "User" = Relationship(
        back_populates="created_tickets",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.created_by]"},
    )
    assignee: Optional["User"] = Relationship(
        back_populates="assigned_tickets",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_to]"},
    )
