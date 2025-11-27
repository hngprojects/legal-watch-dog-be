<<<<<<< HEAD
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship, JSON
from sqlalchemy.dialects.postgresql import JSONB
import uuid


if TYPE_CHECKING:
    from app.api.modules.v1.users.models import User
=======
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.users.models.roles_model import Role
>>>>>>> fix/billing-model-cleanup


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"

<<<<<<< HEAD
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    name: str = Field(max_length=255, nullable=False, index=True)

    settings: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
=======
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    name: str = Field(max_length=255, nullable=False, index=True)

    industry: str = Field(max_length=100, nullable=True)

    settings: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
>>>>>>> fix/billing-model-cleanup
    )

    billing_info: dict = Field(
        default_factory=dict,
<<<<<<< HEAD
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
=======
        sa_column=Column(JSON, nullable=False, server_default="{}"),
>>>>>>> fix/billing-model-cleanup
    )

    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

<<<<<<< HEAD
    users: list["User"] = Relationship(back_populates="organization")
=======
    user_memberships: list["UserOrganization"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    roles: list["Role"] = Relationship(back_populates="organization")
    projects: list["Project"] = Relationship(back_populates="organization")
    invitations: list["Invitation"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
>>>>>>> fix/billing-model-cleanup
