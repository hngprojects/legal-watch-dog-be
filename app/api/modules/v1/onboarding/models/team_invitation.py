from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from enum import Enum

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models import User


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class TeamInvitation(SQLModel, table=True):
    __tablename__ = "team_invitation"

    __table_args__ = (
        UniqueConstraint("org_id", "team_email", name="uq_org_team_email"),
    )

    id: UUID = Field(
        default_factory=uuid4, primary_key=True, index=True, nullable=False
    )
    org_id: UUID = Field(foreign_key="organizations.id", index=True, nullable=False)
    sender_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)

    role: str = Field(nullable=False)
    team_email: str = Field(index=True, nullable=False)

    token: str = Field(
        index=True,
        nullable=False,
        description="Hashed invitation token",
    )

    status: InvitationStatus = Field(
        default=InvitationStatus.PENDING,
        index=True,
        nullable=False,
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    expires_at: Optional[datetime] = Field(
        default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=7)),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    accepted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    organization: Optional["Organization"] = Relationship(back_populates="invitations")
    sender: Optional["User"] = Relationship(back_populates="sent_invitations")
