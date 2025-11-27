<<<<<<< HEAD
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship, JSON
from sqlalchemy.dialects.postgresql import JSONB
import uuid

if TYPE_CHECKING:
    from app.api.modules.v1.users.models.roles_model import Role
    from app.api.modules.v1.organization.models import Organization
=======
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
    from app.api.modules.v1.projects.models.project_user_model import ProjectUser
>>>>>>> fix/billing-model-cleanup


class User(SQLModel, table=True):
    __tablename__ = "users"

<<<<<<< HEAD
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    organization_id: uuid.UUID = Field(
        foreign_key="organizations.id", nullable=False, index=True
    )

    role_id: uuid.UUID = Field(foreign_key="roles.id", nullable=False, index=True)
=======
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
>>>>>>> fix/billing-model-cleanup

    email: str = Field(max_length=255, nullable=False, unique=True, index=True)

    hashed_password: str = Field(max_length=255, nullable=False)

<<<<<<< HEAD
    name: str = Field(index=True, max_length=255)

    # first_name: Optional[str] = Field(
    #     default=None,
    #     max_length=100
    # )

    # last_name: Optional[str] = Field(
    #     default=None,
    #     max_length=100
    # )

    is_active: bool = Field(default=True, nullable=False)
    is_verified: bool = Field(default=False, nullable=False)
=======
    auth_provider: str = Field(
        default="local", max_length=20, nullable=False
    )  # 'local', 'oidc', 'saml'

    name: str = Field(index=True, max_length=255)

    is_active: bool = Field(default=True, nullable=False)
    is_verified: bool = Field(
        default=False, nullable=False, description="Email verification status"
    )
>>>>>>> fix/billing-model-cleanup

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

<<<<<<< HEAD
    organization: "Organization" = Relationship(back_populates="users")
    role: "Role" = Relationship(back_populates="users")
=======
    organization_memberships: list["UserOrganization"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    project_users: list["ProjectUser"] = Relationship(back_populates="user")
    sent_invitations: list["Invitation"] = Relationship(
        back_populates="inviter", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
>>>>>>> fix/billing-model-cleanup
