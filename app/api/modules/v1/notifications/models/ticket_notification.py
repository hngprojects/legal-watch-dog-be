import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Column, DateTime, Field, SQLModel


class TicketNotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class TicketNotification(SQLModel, table=True):
    __tablename__ = "ticket_notifications"

    notification_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    ticket_id: uuid.UUID = Field(foreign_key="tickets.id", index=True, nullable=False)

    user_id: uuid.UUID = Field(foreign_key="users.id", index=True, nullable=False)

    message: str

    status: TicketNotificationStatus = Field(
        default=TicketNotificationStatus.PENDING, nullable=False
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    sent_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True), default=None
    )
