"""Ticket Invitation Model"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field
import uuid
import secrets

if TYPE_CHECKING:
    pass  # Type checking imports removed to avoid F401


class TicketInvitation(SQLModel, table=True):
    """Model for ticket participant invitations"""

    __tablename__ = "ticket_invitations"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    ticket_id: uuid.UUID = Field(foreign_key="tickets.id", nullable=False, index=True)

    invited_by: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)

    invitee_email: str = Field(max_length=255, nullable=False, index=True)

    token: str = Field(max_length=255, nullable=False, unique=True, index=True)

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    is_accepted: bool = Field(default=False, nullable=False)

    is_revoked: bool = Field(default=False, nullable=False)

    revoked_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )

    revoked_by: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id", index=True
    )

    accepted_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for invitation"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def expiry_time(hours: int = 48) -> datetime:
        """Calculate expiry time for invitation (default 48 hours)"""
        return datetime.now(timezone.utc) + timedelta(hours=hours)

    def is_valid(self) -> bool:
        """Check if invitation is still valid"""
        now = datetime.now(timezone.utc)
        return not self.is_revoked and not self.is_accepted and self.expires_at > now

    def revoke(self, revoked_by_id: uuid.UUID) -> None:
        """Revoke the invitation"""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_by = revoked_by_id
        self.updated_at = datetime.now(timezone.utc)

    def accept(self) -> None:
        """Mark invitation as accepted"""
        self.is_accepted = True
        self.accepted_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
