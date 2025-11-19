from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Column
from sqlmodel import SQLModel, Field, Relationship
import uuid

if TYPE_CHECKING:
    from app.api.modules.v1.users.models.roles_model import Role
    from app.api.modules.v1.organization.models import Organization
    from app.api.modules.v1.tickets.models.ticket import Ticket


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    organization_id: uuid.UUID = Field(
        foreign_key="organizations.id", nullable=False, index=True
    )

    role_id: uuid.UUID = Field(foreign_key="roles.id", nullable=False, index=True)

    email: str = Field(max_length=255, nullable=False, unique=True, index=True)

    hashed_password: str = Field(max_length=255, nullable=False)

    auth_provider: str = Field(
        default="local", max_length=20, nullable=False
    )  # 'local', 'oidc', 'saml'

    name: str = Field(index=True, max_length=255)

    is_active: bool = Field(default=True, nullable=False)
    is_verified: bool = Field(default=False, nullable=False)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization: "Organization" = Relationship(back_populates="users")
    role: "Role" = Relationship(back_populates="users")
    created_tickets: list["Ticket"] = Relationship(
        back_populates="creator",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.created_by]"},
    )
    assigned_tickets: list["Ticket"] = Relationship(
        back_populates="assignee",
        sa_relationship_kwargs={"foreign_keys": "[Ticket.assigned_to]"},
    )
