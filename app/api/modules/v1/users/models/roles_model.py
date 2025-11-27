<<<<<<< HEAD
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship, JSON
from sqlalchemy.dialects.postgresql import JSONB
import uuid

if TYPE_CHECKING:
    from app.api.modules.v1.users.models import User
=======
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.organization_model import Organization
>>>>>>> fix/billing-model-cleanup


class Role(SQLModel, table=True):
    __tablename__ = "roles"
<<<<<<< HEAD

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    name: str = Field(max_length=50, nullable=False, unique=True, index=True)
=======
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_role_name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    organization_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="organizations.id",
        nullable=True,
        index=True,
        description="Null for global roles, UUID for organization-specific roles",
    )

    name: str = Field(max_length=50, nullable=False, index=True)
>>>>>>> fix/billing-model-cleanup

    description: Optional[str] = Field(default=None, max_length=500)

    permissions: dict = Field(
        default_factory=dict,
<<<<<<< HEAD
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
=======
        sa_column=Column(JSON, nullable=False, server_default="{}"),
>>>>>>> fix/billing-model-cleanup
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

<<<<<<< HEAD
    users: list["User"] = Relationship(back_populates="role")
=======
    organization: "Organization" = Relationship(back_populates="roles")
    invitations: list["Invitation"] = Relationship(back_populates="role")
>>>>>>> fix/billing-model-cleanup
