import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
    from app.api.modules.v1.projects.models.project_user_model import ProjectUser


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    email: str = Field(max_length=255, nullable=False, unique=True, index=True)

    hashed_password: str = Field(max_length=255, nullable=False)

    auth_provider: str = Field(
        default="local", max_length=20, nullable=False
    )  # 'local', 'oidc', 'saml'

    name: str = Field(index=True, max_length=255)

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
