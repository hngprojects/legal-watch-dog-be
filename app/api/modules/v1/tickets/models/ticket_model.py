import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from pydantic import field_validator
from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

from app.api.modules.v1.tickets.models.comment_model import Comment


class ExternalParticipant(SQLModel, table=True):
    """
    External participants invited to a ticket (non-users with guest access).

    These are people who do NOT have accounts in the system but need access
    to a specific ticket. They access via a secure JWT token (magic link).
    """

    __tablename__ = "external_participants"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )
    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        nullable=False,
        index=True,
        description="The ticket this guest can access (strict scope)",
    )
    email: str = Field(
        max_length=255,
        nullable=False,
        index=True,
        description="Email address of the external participant",
    )
    role: str = Field(
        default="Guest",
        max_length=100,
        nullable=False,
        description="Role description (e.g., 'Legal Counsel', 'Consultant')",
    )
    token_hash: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Hash of the JWT token for revocation purposes",
    )
    invited_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="User who invited this external participant",
    )
    invited_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    last_accessed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the participant last accessed the ticket",
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        description="Whether this guest access is still active (revoked when ticket closes)",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the guest access expires",
    )

    ticket: "Ticket" = Relationship(
        back_populates="external_participants",
        sa_relationship_kwargs={"foreign_keys": "[ExternalParticipant.ticket_id]"},
    )
    invited_by_user: "User" = Relationship(
        back_populates="invited_external_participants",
        sa_relationship_kwargs={"foreign_keys": "[ExternalParticipant.invited_by_user_id]"},
    )

    comments: list["Comment"] = Relationship(
        back_populates="participant",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source
    from app.api.modules.v1.tickets.models.comment_model import Comment
    from app.api.modules.v1.users.models.users_model import User


class TicketStatus(str, Enum):
    """Status of a ticket in the workflow."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


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
    content: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Content from the detected changes or observations",
    )

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

    change_diff_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="change_diff.diff_id",
        index=True,
        nullable=True,
        description="Reference to the change diff that this ticket is based on",
    )

    data_revision_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="data_revisions.id",
        index=True,
        nullable=True,
        description="Optional reference to the data revision that triggered this ticket",
    )

    source_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="sources.id",
        index=True,
        nullable=True,
        description="Source where the change was detected",
    )

    created_by_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="User who created this ticket (null if auto-generated)",
    )

    assigned_by_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="User who assigns this ticket to others",
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

    created_by_user: Optional["User"] = Relationship(
        back_populates="created_tickets",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.created_by_user_id]"},
    )
    assigned_by_user: Optional["User"] = Relationship(
        back_populates="assigned_tickets_by",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_by_user_id]"},
    )
    assigned_to_user: Optional["User"] = Relationship(
        back_populates="assigned_tickets",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_to_user_id]"},
    )
    comments: list["Comment"] = Relationship(
        back_populates="ticket",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    organization: "Organization" = Relationship(back_populates="tickets")
    project: "Project" = Relationship(back_populates="tickets")
    change_diff: Optional["ChangeDiff"] = Relationship()
    data_revision: Optional["DataRevision"] = Relationship(back_populates="tickets")
    source: Optional["Source"] = Relationship(back_populates="tickets")
    external_participants: list["ExternalParticipant"] = Relationship(
        back_populates="ticket",
        sa_relationship_kwargs={
            "foreign_keys": "[ExternalParticipant.ticket_id]",
            "cascade": "all, delete-orphan",
        },
    )

    @field_validator("created_by_user_id")
    @classmethod
    def validate_creator_for_manual_tickets(cls, v, info):
        """Validate that manual tickets have a creator."""
        is_manual = info.data.get("is_manual", True)
        if is_manual and v is None:
            raise ValueError("Manual tickets must have a created_by_user_id")
        return v
