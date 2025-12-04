import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.ticket_model import Ticket
    from app.api.modules.v1.users.models.users_model import User


class MagicLink(SQLModel, table=True):
    """
    Temporary access tokens that allow guests to access specific tickets
    without creating an account or logging in.
    """

    __tablename__ = "magic_links"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    token: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
        index=True,
        description="Unique token for URL access",
    )

    guest_email: str = Field(
        max_length=255,
        nullable=False,
        index=True,
        description="Email of the guest this link is for",
    )

    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        nullable=False,
        index=True,
        description="Ticket this link provides access to",
    )

    created_by_user_id: uuid.UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="User who created this magic link",
    )

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When this link expires and becomes invalid",
    )

    used_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When this link was first used (null if unused)",
    )

    max_uses: int = Field(
        default=1,
        nullable=False,
        description="Maximum number of times this link can be used (0 = unlimited)",
    )

    use_count: int = Field(
        default=0, nullable=False, description="Number of times this link has been used"
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    ticket: "Ticket" = Relationship()
    created_by_user: "User" = Relationship()
