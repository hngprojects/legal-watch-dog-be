from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe Checkout session"""

    plan: Literal["monthly", "yearly"] = Field(..., description="Subscription plan type")
    success_url: Optional[str] = Field(None, description="URL to redirect after successful payment")
    cancel_url: Optional[str] = Field(None, description="URL to redirect if user cancels")

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        if v not in ["monthly", "yearly"]:
            raise ValueError("Plan must be either 'monthly' or 'yearly'")
        return v


class PortalSessionRequest(BaseModel):
    """Request to create a Stripe Customer Portal session"""

    return_url: Optional[str] = Field(None, description="URL to return to after portal session")


class SubscriptionUpdateRequest(BaseModel):
    """Request to update subscription plan"""

    new_plan: Literal["monthly", "yearly"] = Field(..., description="New subscription plan")
    prorate: bool = Field(True, description="Whether to prorate the subscription change")

    @field_validator("new_plan")
    @classmethod
    def validate_new_plan(cls, v: str) -> str:
        if v not in ["monthly", "yearly"]:
            raise ValueError("New plan must be either 'monthly' or 'yearly'")
        return v


class SubscriptionCancelRequest(BaseModel):
    """Request to cancel a subscription"""

    cancel_at_period_end: bool = Field(
        True,
        description=("If True, cancel at end of billing period. If False, cancel immediately."),
    )

    cancellation_reason: Optional[str] = Field(
        None, max_length=500, description="Reason for cancellation"
    )


class AttachPaymentMethodRequest(BaseModel):
    """Request to attach a payment method"""

    payment_method_id: str = Field(..., description="Stripe payment method ID")
    set_as_default: bool = Field(True, description="Whether to set as default payment method")
