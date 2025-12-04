import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class Notification(SQLModel, table=True):
    __tablename__ = "revision_notifications"

    # SQLModel handles the UUID primary key automatically
    notification_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    revision_id: uuid.UUID = Field(foreign_key="data_revisions.id")
    user_id: uuid.UUID = Field(foreign_key="users.id")

    message: str
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    sent_at: Optional[datetime] = None
