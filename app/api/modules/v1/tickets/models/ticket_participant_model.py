import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.guest_model import Guest
    from app.api.modules.v1.tickets.models.ticket_model import Ticket
    from app.api.modules.v1.users.models.users_model import User


class ParticipantType(str, Enum):
    """Type of participant - internal user or external guest."""

    USER = "user"
    GUEST = "guest"


class AccessLevel(str, Enum):
    """Permission level for ticket participants."""

    VIEWER = "viewer"
    COMMENTER = "commenter"
    EDITOR = "editor"


class TicketParticipant(SQLModel, table=True):
    """
    Links users or guests to tickets with specific access permissions.
    This enables both internal team members and external specialists
    to collaborate on tickets with controlled access.
    """

    __tablename__ = "ticket_participants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        nullable=False,
        index=True,
        description="Ticket this participant has access to",
    )

    participant_type: ParticipantType = Field(
        sa_column=Column(SQLEnum(ParticipantType), nullable=False),
        description="Whether participant is a user or guest",
    )

    participant_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        description="Reference to User if participant_type is 'user'",
    )

    participant_guest_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="guests.id",
        nullable=True,
        index=True,
        description="Reference to Guest if participant_type is 'guest'",
    )

    access_level: AccessLevel = Field(
        sa_column=Column(SQLEnum(AccessLevel), nullable=False),
        default=AccessLevel.VIEWER,
        description="Permission level for this participant",
    )

    invited_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="User who invited/added this participant",
    )

    invited_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this participant was added to the ticket",
    )

    is_assigned_responder: bool = Field(
        default=False,
        nullable=False,
        description="Whether this participant is the primary assigned responder",
    )

    ticket: "Ticket" = Relationship(back_populates="participants")
    user: Optional["User"] = Relationship()
    guest: Optional["Guest"] = Relationship(back_populates="ticket_participations")
    invited_by_user: "User" = Relationship()
