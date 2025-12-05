import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
    from app.api.modules.v1.projects.models.project_user_model import ProjectUser
    from app.api.modules.v1.tickets.models.ticket_model import ExternalParticipant, Ticket



class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    email: str = Field(max_length=255, nullable=False, unique=True, index=True)

    hashed_password: Optional[str] = Field(default=None, max_length=255, nullable=True)

    auth_provider: str = Field(
        default="local", max_length=20, nullable=False
    )  # 'local', 'oidc', 'saml'

    name: str = Field(index=True, max_length=255)
    provider_user_id: Optional[str] = Field(default=None, index=True)
    profile_picture_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to user's profile picture from OAuth provider",
    )
    provider_profile_data: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Raw OAuth provider profile data (name, picture, etc.)",
    )

    avatar_url: Optional[str] = Field(None, max_length=500, description="User avatar image URL")

    is_active: bool = Field(default=True, nullable=False)
    is_verified: bool = Field(
        default=False, nullable=False, description="Email verification status"
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization_memberships: list["UserOrganization"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    project_users: list["ProjectUser"] = Relationship(back_populates="user")
    sent_invitations: list["Invitation"] = Relationship(
        back_populates="inviter", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    created_tickets: list["Ticket"] = Relationship(
        back_populates="created_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.created_by_user_id]"},
    )
    assigned_tickets_by: list["Ticket"] = Relationship(
        back_populates="assigned_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_by_user_id]"},
    )
    assigned_tickets: list["Ticket"] = Relationship(
        back_populates="assigned_to_user",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_to_user_id]"},
    )
    invited_external_participants: list["ExternalParticipant"] = Relationship(
        back_populates="invited_by_user",
        sa_relationship_kwargs={"foreign_keys": "[ExternalParticipant.invited_by_user_id]"},
    )

