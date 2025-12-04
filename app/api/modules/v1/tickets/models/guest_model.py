import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.ticket_participant_model import TicketParticipant
    from app.api.modules.v1.users.models.users_model import User


class Guest(SQLModel, table=True):
    """
    External users who don't have accounts but are invited to participate in tickets.
    They authenticate via magic links instead of regular login.
    """

    __tablename__ = "guests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    email: str = Field(
        max_length=255, nullable=False, index=True, description="Email address of the guest"
    )
    name: Optional[str] = Field(
        default=None, max_length=255, nullable=True, description="Full name of the guest (optional)"
    )

    invited_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="User who invited this guest",
    )

    invited_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the guest was first invited",
    )
    last_active: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last time the guest accessed any ticket",
    )

    invited_by_user: "User" = Relationship()
    ticket_participations: list["TicketParticipant"] = Relationship(
        back_populates="guest", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
