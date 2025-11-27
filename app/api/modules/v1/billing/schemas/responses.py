from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentMethodResponse(BaseModel):
    """Payment method information"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stripe_pm_id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime


class SubscriptionResponse(BaseModel):
    """Current subscription information"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stripe_subscription_id: str
    plan: Literal["monthly", "yearly"]
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    canceled_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime


class InvoiceResponse(BaseModel):
    """Invoice information"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stripe_invoice_id: str
    amount: Decimal
    currency: str
    status: str
    paid: bool
    invoice_pdf_url: Optional[str] = None
    hosted_invoice_url: Optional[str] = None
    invoice_date: datetime
    created_at: datetime


class NextInvoiceResponse(BaseModel):
    """Upcoming invoice preview"""

    amount_due: int  # in cents
    currency: str
    billing_date: datetime
    line_items: List[dict]


class BillingSummaryResponse(BaseModel):
    """Complete billing account summary"""

    model_config = ConfigDict(from_attributes=True)

    # Core billing info
    billing_account_id: UUID
    organization_id: UUID
    stripe_customer_id: Optional[str] = None
    status: Literal["trialing", "active", "past_due", "blocked", "canceled"]

    # Trial information
    trial_ends_at: Optional[datetime] = None
    trial_days_remaining: int = 0
    is_trial_expired: bool = False

    # Subscription information
    has_active_subscription: bool = False
    current_subscription: Optional[SubscriptionResponse] = None
    current_period_end: Optional[datetime] = None

    # Financial information
    next_invoice: Optional[NextInvoiceResponse] = None
    payment_methods: List[PaymentMethodResponse] = []
    recent_invoices: List[InvoiceResponse] = []

    # Timestamps
    created_at: datetime
    blocked_at: Optional[datetime] = None


class CheckoutSessionResponse(BaseModel):
    """Stripe Checkout session response"""

    checkout_url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    """Stripe Customer Portal session response"""

    portal_url: str


class BillingMetricsResponse(BaseModel):
    """Admin billing metrics"""

    total_accounts: int
    active_subscriptions: int
    trial_accounts: int
    past_due_accounts: int
    blocked_accounts: int
    monthly_recurring_revenue: Decimal
    annual_recurring_revenue: Decimal
    churn_rate: Optional[float] = None
    average_revenue_per_user: Optional[Decimal] = None


class StandardResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None
    detail: Optional[dict] = None
