import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.ticket_model import Ticket


class TicketExternalAccess(SQLModel, table=True):
    """
    Tokenized access records for external users to view tickets.

    Allows non-organization members to access specific tickets through
    secure, time-limited tokens without requiring full system access.

    Attributes:
        id: UUID primary key
        ticket_id: Reference to the ticket being shared
        token: Unique secure token for accessing the ticket
        email: Email address of the external user (optional, for tracking)
        created_by_user_id: User who created this external access
        expires_at: When this access token expires (nullable for permanent access)
        last_accessed_at: Last time this token was used
        access_count: Number of times this token has been used
        is_active: Whether this access is currently valid
        revoked_at: When this access was revoked (if applicable)
        created_at: When this access was created
        ticket: Relationship to the ticket
    """

    __tablename__ = "ticket_external_access"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )

    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        nullable=False,
        index=True,
    )

    token: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
        index=True,
        description="Secure token for accessing the ticket",
    )

    email: Optional[str] = Field(
        default=None,
        max_length=255,
        index=True,
        description="Email of external user (optional, for tracking)",
    )

    created_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="User who created this external access",
    )

    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Expiration time for this access token",
    )

    last_accessed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last time this token was used",
    )

    access_count: int = Field(
        default=0,
        nullable=False,
        description="Number of times this token has been accessed",
    )

    is_active: bool = Field(
        default=True,
        nullable=False,
        index=True,
        description="Whether this access is currently valid",
    )

    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When this access was revoked",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    ticket: "Ticket" = Relationship(back_populates="external_accesses")
