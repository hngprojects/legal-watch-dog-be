import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from app.api.modules.v1.billing.models.billing_account import BillingStatus

_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


class BillingAccountCreateRequest(BaseModel):
    currency: Optional[str] = Field("USD", max_length=3, description="ISO currency code")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().upper()
        if not _CURRENCY_RE.match(v):
            raise ValueError("currency must be a 3-letter code (e.g. USD, GBP, NGN)")
        return v


class BillingAccountResponse(BaseModel):
    id: UUID
    organization_id: UUID
    status: str
    currency: str
    default_payment_method_id: Optional[UUID] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    trial_starts_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentMethodCreateRequest(BaseModel):
    stripe_payment_method_id: str = Field(..., description="Stripe PaymentMethod ID (pm_...)")
    card_brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = Field(False, description="Mark this method as default for the account")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("stripe_payment_method_id")
    @classmethod
    def validate_pm_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("stripe_payment_method_id must be provided")
        v = v.strip()
        if not v.startswith("pm_"):
            raise ValueError(
                "stripe_payment_method_id must look like a Stripe PM id (starts with 'pm_')"
            )
        return v

    @field_validator("last4")
    @classmethod
    def validate_last4(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v.isdigit() or len(v) != 4:
            raise ValueError("last4 must be exactly 4 digits")
        return v

    @field_validator("exp_month")
    @classmethod
    def validate_exp_month(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if not (1 <= v <= 12):
            raise ValueError("exp_month must be between 1 and 12")
        return v

    @field_validator("exp_year")
    @classmethod
    def validate_exp_year(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if v < 2023 or v > 2100:
            raise ValueError("exp_year seems invalid")
        return v

    @field_validator("card_brand")
    @classmethod
    def validate_card_brand(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) == 0:
            return None
        if len(v) > 50:
            raise ValueError("card_brand must be <= 50 characters")
        return v


class PaymentMethodResponse(BaseModel):
    id: UUID
    billing_account_id: UUID
    stripe_payment_method_id: str
    card_brand: Optional[str]
    last4: Optional[str]
    exp_month: Optional[int]
    exp_year: Optional[int]
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreateRequest(BaseModel):
    product_id: str = Field(
        ...,
        description="ID of the product / plan to invoice for.",
        examples=["prod_TUT6IlTqoSvv5D"],
    )
    quantity: int = 1
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: UUID
    billing_account_id: UUID
    amount_due: int
    amount_paid: int
    currency: str
    status: str
    stripe_invoice_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    hosted_invoice_url: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BillingPlan(str, Enum):
    """Supported subscription billing cadences."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


class CheckoutSessionCreateRequest(BaseModel):
    """
    Request body for starting a Stripe Checkout session.
    """

    plan: BillingPlan
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CheckoutSessionResponse(BaseModel):
    """
    Response containing the Stripe Checkout session details.
    """

    checkout_url: AnyHttpUrl
    session_id: str


class SubscriptionStatusResponse(BaseModel):
    billing_account_id: UUID
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    status: BillingStatus
    cancel_at_period_end: bool = False

    trial_starts_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None

    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    next_billing_at: Optional[datetime] = None


class SubscriptionCancelRequest(BaseModel):
    cancel_at_period_end: bool = True


class SubscriptionChangePlanRequest(BaseModel):
    plan: BillingPlan


class BillingPlanInfo(BaseModel):
    code: BillingPlan
    label: str
    price_id: str
    product_id: str
    interval: Literal["month", "year"]
    currency: str
    amount: int
