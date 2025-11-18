from typing import Optional, TYPE_CHECKING, List
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from enum import Enum

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship, backref
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
    """Represents an invitation sent to a user to join an organization's team.

    Fields:
    - id (UUID): Primary key.
    - org_id (UUID): Foreign key to `organizations.id`.
    - sender_id (UUID): Foreign key to `users.id` who created the invite.
    - role (str): Role to grant when the invite is accepted.
    - team_email (str): The invited email address.
    - token (str): Invitation token (store hashed for security).
    - status (InvitationStatus): Current invite state.
    - created_at (datetime): When the invite was created (UTC).
    - expires_at (Optional[datetime]): When the invite expires.
    - accepted_at (Optional[datetime]): When the invite was accepted.

    Usage:
    - Created by the onboarding service; the token is sent to `team_email`.
    - Acceptance validates the token, assigns the role, sets `accepted_at`,
        and updates `status`.
    """

    __tablename__ = "team_invitation"

    __table_args__ = (
        UniqueConstraint("org_id", "team_email", name="uq_org_team_email"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)

    # FK to organizations.id
    org_id: UUID = Field(foreign_key="organizations.id", index=True, nullable=False)

    # FK to users.id (sender)
    sender_id: UUID = Field(foreign_key="users.id", index=True, nullable=False)

    role: str = Field(nullable=False, description="Role to assign when accepted")

    team_email: str = Field(index=True, nullable=False, description="Email invited")

    # store a token (prefer hashed)
    token: str = Field(index=True, nullable=False, description="Invitation token (store hashed for security)")

    status: InvitationStatus = Field(default=InvitationStatus.PENDING, index=True, nullable=False)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    expires_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=7),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Expiration timestamp (2 days by default)",
    )

    accepted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

  

    # organization: Optional["Organization"] = Relationship(back_populates="invitations")
    # sender: Optional["User"] = Relationship(back_populates="sent_invitations")

    

