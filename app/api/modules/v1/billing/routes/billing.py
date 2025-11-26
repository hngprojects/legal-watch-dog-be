import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.auth.dependencies import get_current_user
from app.api.modules.v1.billing.schemas.requests import (
    AttachPaymentMethodRequest,
    CheckoutSessionRequest,
    PortalSessionRequest,
    SubscriptionCancelRequest,
    SubscriptionUpdateRequest,
)
from app.api.modules.v1.billing.schemas.responses import (
    BillingSummaryResponse,
    CheckoutSessionResponse,
    InvoiceResponse,
    PaymentMethodResponse,
    PortalSessionResponse,
    StandardResponse,
    SubscriptionResponse,
)
from app.api.modules.v1.billing.services.billing_service import BillingService
from app.api.modules.v1.users.models import User

setup_logging()
logger = logging.getLogger(__name__)  


router = APIRouter(prefix="/organizations/{org_id}/billing", tags=["Billing"])


def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    """Dependency to get BillingService instance"""
    return BillingService(db)

# BILLING ACCOUNT ENDPOINTS 

@router.post(
    "/",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or get billing account",
    description="Creates a billing account with 14-day free trial if it doesn't exist. Idempotent."
)
async def create_or_get_billing_account(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> StandardResponse:
    """Create or retrieve billing account"""
    logger.info("POST /billing - Create or get billing account", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id)
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        billing_account = await billing_service.get_or_create_billing_account(
            organization_id=org_id,
            user_email=current_user.email,
            organization_name=current_user.organization.name if current_user.organization else None
        )

        return StandardResponse(
            success=True,
            data={
                "billing_account_id": str(billing_account.id),
                "organization_id": str(billing_account.organization_id),
                "status": billing_account.status,
                "trial_ends_at": (
                    billing_account.trial_ends_at.isoformat()
                    if billing_account.trial_ends_at else None
                ),
                "stripe_customer_id": billing_account.stripe_customer_id
            },
            message="Billing account retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create/get billing account", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process billing account"
        )

@router.get(
    "/",
    response_model=BillingSummaryResponse,
    summary="Get billing summary"
)
async def get_billing_summary(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> BillingSummaryResponse:
    """Get complete billing summary"""
    logger.info("GET /billing - Fetch billing summary", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id)
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        summary = await billing_service.get_billing_summary(organization_id=org_id)
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch billing summary", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve billing summary"
        )

@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Stripe Checkout session"
)
async def create_checkout_session(
    org_id: UUID,
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> CheckoutSessionResponse:
    """Create Stripe Checkout session"""
    logger.info("POST /checkout - Create checkout session", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id),
        "plan": request.plan
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        checkout_session = await billing_service.create_checkout_session(
            organization_id=org_id,
            plan=request.plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )

        return checkout_session

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create checkout session", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.post(
    "/portal",
    response_model=PortalSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Stripe Customer Portal session"
)
async def create_portal_session(
    org_id: UUID,
    request: PortalSessionRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> PortalSessionResponse:
    """Create Stripe Customer Portal session"""
    logger.info("POST /portal - Create portal session", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id)
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        portal_session = await billing_service.create_portal_session(
            organization_id=org_id,
            return_url=request.return_url
        )

        return portal_session

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create portal session", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )

@router.post(
    "/payment-methods",
    response_model=PaymentMethodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach payment method"
)
async def attach_payment_method(
    org_id: UUID,
    request: AttachPaymentMethodRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> PaymentMethodResponse:
    """Attach payment method"""
    logger.info("POST /payment-methods - Attach payment method", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id),
        "payment_method_id": request.payment_method_id
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        payment_method = await billing_service.attach_payment_method(
            organization_id=org_id,
            payment_method_id=request.payment_method_id,
            set_as_default=request.set_as_default
        )

        return payment_method

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to attach payment method", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to attach payment method"
        )

@router.patch(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Update subscription plan"
)
async def update_subscription(
    org_id: UUID,
    request: SubscriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> SubscriptionResponse:
    """Update subscription"""
    logger.info("PATCH /subscription - Update subscription", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id),
        "new_plan": request.new_plan,
        "prorate": request.prorate
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        subscription = await billing_service.update_subscription(
            organization_id=org_id,
            new_plan=request.new_plan,
            prorate=request.prorate
        )

        return subscription

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update subscription", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update subscription"
        )

@router.post(
    "/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel subscription"
)
async def cancel_subscription(
    org_id: UUID,
    request: SubscriptionCancelRequest,
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> SubscriptionResponse:
    """Cancel subscription"""
    logger.info("POST /cancel - Cancel subscription", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id),
        "cancel_at_period_end": request.cancel_at_period_end,
        "reason": request.cancellation_reason
    })

    # Validate organization ownership
    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        subscription = await billing_service.cancel_subscription(
            organization_id=org_id,
            cancel_at_period_end=request.cancel_at_period_end,
            cancellation_reason=request.cancellation_reason
        )

        return subscription

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel subscription", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )

@router.get(
    "/invoices",
    response_model=List[InvoiceResponse],
    summary="List invoices"
)
async def list_invoices(
    org_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    billing_service: BillingService = Depends(get_billing_service)
) -> List[InvoiceResponse]:
    """List invoices"""
    logger.info("GET /invoices - List invoices", extra={
        "org_id": str(org_id),
        "user_id": str(current_user.id),
        "limit": limit,
        "offset": offset
    })

    billing_service.validate_organization_ownership(org_id, current_user.organization_id)

    try:
        invoices = await billing_service.list_invoices(
            organization_id=org_id,
            limit=limit,
            offset=offset
        )

        return invoices

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list invoices", exc_info=True, extra={
            "org_id": str(org_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve invoices"
        )
