"""
Project Model

NOTE: This is a minimal implementation created by the Ticketing System team (TS-01).
The Projects team should feel free to extend this model with additional fields,
relationships, and business logic as needed for full project management functionality.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship
import uuid

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.tickets.models.ticket import Ticket


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    organization_id: uuid.UUID = Field(
        foreign_key="organizations.id", nullable=False, index=True
    )

    name: str = Field(max_length=255, nullable=False, index=True)

    description: Optional[str] = Field(default=None, max_length=1000)

    ai_prompt: Optional[str] = Field(default=None)

    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization: "Organization" = Relationship(back_populates="projects")
    tickets: list["Ticket"] = Relationship(back_populates="project")
