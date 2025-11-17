from sqlmodel import SQLModel, Field, Column, DateTime
from datetime import datetime, UTC


class WaitlistSubscriber(SQLModel, table=True):
    """Database model for storing waitlist subscriber information.

    Attributes:
        email: Subscriber's email address (unique primary key, indexed).
            This is the unique identifier and primary search key for the table.
        name: Subscriber's  name (cannot be empty).
        signup_date: Timestamp when the subscriber joined the waitlist.
            Automatically set to current UTC time on creation (timezone-aware).
        source: Source/origin of the signup (e.g., "twitter", "email_campaign",
            "website", "referral"). Defaults to "unknown" if not provided.
    """

    __tablename__ = "waitlist_subscriber"

    email: str = Field(primary_key=True, index=True, unique=True)
    name: str = Field(
        nullable=False, min_length=1, description="Subscriber's name (cannot be empty)"
    )
    source: str = Field(default="unknown")
    signup_date: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=lambda: datetime.now(UTC)
        )
    )
