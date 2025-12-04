import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.guest_model import Guest
    from app.api.modules.v1.tickets.models.ticket_model import Ticket
    from app.api.modules.v1.users.models.users_model import User


class TicketComment(SQLModel, table=True):
    """
    Comments and discussions on tickets.
    Can be created by both internal users and external guests.
    """

    __tablename__ = "ticket_comments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        nullable=False,
        index=True,
        description="Ticket this comment belongs to",
    )

    author_type: str = Field(
        default="user", nullable=False, description="Type of author (user or guest)"
    )

    author_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        description="User ID if author is an internal user",
    )

    author_guest_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="guests.id",
        nullable=True,
        index=True,
        description="Guest ID if author is an external guest",
    )

    author_name: str = Field(
        max_length=255,
        nullable=False,
        description="Display name of the author (for display purposes)",
    )

    author_email: Optional[str] = Field(
        default=None, max_length=255, nullable=True, description="Email of the author (for guests)"
    )

    content: str = Field(
        sa_column=Column(Text, nullable=False), description="The comment text/content"
    )

    is_internal: bool = Field(
        default=False,
        nullable=False,
        description="Whether this is an internal comment (not visible to guests)",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    ticket: "Ticket" = Relationship(back_populates="comments")
    author_user: Optional["User"] = Relationship()
    author_guest: Optional["Guest"] = Relationship()
