from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Column, JSON
from sqlmodel import SQLModel, Field, Relationship
import uuid


if TYPE_CHECKING:
    from app.api.modules.v1.users.models.users_model import User
    from app.api.modules.v1.users.models.roles_model import Role
    from app.api.modules.v1.projects.models.project import Project
    from app.api.modules.v1.tickets.models.ticket import Ticket


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    name: str = Field(max_length=255, nullable=False, index=True)

    industry: str = Field(max_length=100, nullable=True)

    settings: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
    )

    billing_info: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
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

    users: list["User"] = Relationship(back_populates="organization")
    roles: list["Role"] = Relationship(back_populates="organization")
    projects: list["Project"] = Relationship(back_populates="organization")
    tickets: list["Ticket"] = Relationship(back_populates="organization")
