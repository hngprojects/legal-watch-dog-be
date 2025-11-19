from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import DateTime, Column
from sqlalchemy.sql import func
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import EmailStr


class Waitlist(SQLModel, table=True):
    __tablename__ = "waitlist"
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_email: str = Field(unique=True, index=True, max_length=255)
    organization_name: str = Field(index=True, max_length=255)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # List of subscribers for this organization
    subscribers: List["WaitlistSubscriber"] = Relationship(
        back_populates="organization"
    )


class WaitlistSubscriber(SQLModel, table=True):
    __tablename__ = "waitlist_subscriber"

    email: EmailStr = Field(primary_key=True, index=True)
    name: str = Field(min_length=1)
    source: Optional[str] = Field(default="unknown")
    signup_date: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
    )

    # Foreign key linking subscriber to organization
    organization_email: str = Field(foreign_key="waitlist.organization_email")
    organization: Optional[Waitlist] = Relationship(back_populates="subscribers")
