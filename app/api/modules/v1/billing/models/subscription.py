import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.billing.models.billing_account import BillingAccount


class SubscriptionStatus(str, Enum):
    """Subscription statuses matching Stripe's subscription statuses."""

    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    PAUSED = "paused"


class SubscriptionPlan(str, Enum):
    """Subscription plan types."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


class Subscription(SQLModel, table=True):
    """
    Subscription record linked to a billing account.
    """

    __tablename__ = "billing_subscriptions"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )

    billing_account_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("billing_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    stripe_subscription_id: str = Field(
        max_length=255, nullable=False, index=True, unique=True
    )

    stripe_price_id: Optional[str] = Field(default=None, max_length=255, nullable=True)

    plan: SubscriptionPlan = Field(default=SubscriptionPlan.MONTHLY, nullable=False)

    status: SubscriptionStatus = Field(
        default=SubscriptionStatus.ACTIVE, nullable=False
    )

    current_period_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    current_period_end: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    cancel_at_period_end: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False)
    )

    canceled_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    ended_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    trial_start: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    trial_end: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))

    metadata_: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False, server_default="{}"),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    billing_account: "BillingAccount" = Relationship(back_populates="subscriptions")
