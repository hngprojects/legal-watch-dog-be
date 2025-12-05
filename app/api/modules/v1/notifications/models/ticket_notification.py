import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Column, DateTime, Field, SQLModel


class TicketNotificationStatus(str, enum.Enum):
    """Status values representing the state of a ticket notification."""

    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class TicketNotification(SQLModel, table=True):
    """
    Ticket notification model for storing activity-based notifications related to tickets.

    This model ensures idempotent notification storage by creating a unique record
    per user–ticket event, preventing duplicated notifications for the same activity.

    Attributes:
        notification_id:
            Unique identifier for the notification entry.

        ticket_id:
            Reference to the ticket that triggered this notification.

        user_id:
            The user who should receive the notification.

        message:
            Full text of the notification explaining the ticket activity.

        status:
            Current status of the notification (PENDING, SENT, FAILED).

        created_at:
            Timestamp representing when the notification record was created.

        sent_at:
            Timestamp representing when the notification was actually delivered.
            This remains `None` until delivery is attempted.
    """

    __tablename__ = "ticket_notifications"

    notification_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )

    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        index=True,
        nullable=False,
    )

    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True,
        nullable=False,
    )

    message: str

    status: TicketNotificationStatus = Field(
        default=TicketNotificationStatus.PENDING,
        nullable=False,
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    sent_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )
