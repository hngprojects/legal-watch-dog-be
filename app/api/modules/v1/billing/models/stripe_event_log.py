import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel


class StripeEventLog(SQLModel, table=True):
    __tablename__ = "stripe_event_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    event_id: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
        index=True,
        description="Unique Stripe event ID",
    )

    type: str = Field(
        max_length=255,
        nullable=False,
        index=True,
        description="stripe event type e.g. invoice.paid",
    )

    object_type: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Stripe object type from event.data.object",
    )

    payload: Dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False),
        description="Full Stripe webhook JSON payload",
    )

    processed: bool = Field(default=False, nullable=False)

    processed_success: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False),
        description="Whether event processing was successful",
    )

    processed_at: Optional[datetime] = Field(
        default=None, nullable=True, description="Timestamp when event was processed"
    )

    error_message: Optional[str] = Field(
        default=None, sa_column=Column(Text), description="Processing error if any"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
