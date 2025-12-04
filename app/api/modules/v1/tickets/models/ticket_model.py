import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.users.models.users_model import User


class TicketStatus(str, Enum):
    """Status of a ticket in the workflow."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketPriority(str, Enum):
    """Priority level for a ticket."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Ticket(SQLModel, table=True):
    """
    Ticket for tracking and discussing detected changes or manual observations.
    Tickets provide a collaborative workspace for Core Users to discuss
    detected changes, attach context, and invite external participants
    for scoped collaboration without granting full system access.
    """

    __tablename__ = "tickets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    title: str = Field(max_length=255, nullable=False, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    status: TicketStatus = Field(
        default=TicketStatus.OPEN,
        nullable=False,
        index=True,
    )
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM,
        nullable=False,
        index=True,
    )

    is_manual: bool = Field(
        default=True,
        nullable=False,
        description="True if the ticket was manually created, False if auto-generated",
    )

    data_revision_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="data_revisions.id",
        index=True,
        nullable=True,
        description="Optional reference to the data revision that triggered this ticket",
    )

    created_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True,
        nullable=False,
        description="User who created this ticket",
    )

    assigned_to_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="User assigned to handle this ticket",
    )

    organization_id: uuid.UUID = Field(
        foreign_key="organizations.id",
        index=True,
        nullable=False,
    )

    project_id: uuid.UUID = Field(
        foreign_key="projects.id",
        index=True,
        nullable=False,
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    closed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    created_by_user: "User" = Relationship(
        back_populates="created_tickets",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.created_by_user_id]"},
    )
    assigned_to_user: Optional["User"] = Relationship(
        back_populates="assigned_tickets",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_to_user_id]"},
    )
    organization: "Organization" = Relationship(back_populates="tickets")
    project: "Project" = Relationship(back_populates="tickets")
    data_revision: Optional["DataRevision"] = Relationship(back_populates="tickets")