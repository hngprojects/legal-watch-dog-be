import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.auth import require_billing_admin
from app.api.db.database import get_db
from app.api.modules.v1.billing.models.billing_account import BillingAccount
from app.api.modules.v1.billing.routes.docs.billing_routes_docs import (
    add_payment_method_custom_errors,
    add_payment_method_custom_success,
    add_payment_method_responses,
    cancel_subscription_custom_errors,
    cancel_subscription_custom_success,
    cancel_subscription_responses,
    change_subscription_plan_custom_errors,
    change_subscription_plan_custom_success,
    change_subscription_plan_responses,
    create_billing_account_custom_errors,
    create_billing_account_custom_success,
    create_billing_account_responses,
    create_checkout_custom_errors,
    create_checkout_custom_success,
    create_checkout_responses,
    create_invoice_record_custom_errors,
    create_invoice_record_custom_success,
    create_invoice_record_responses,
    delete_payment_method_custom_errors,
    delete_payment_method_custom_success,
    delete_payment_method_responses,
    get_billing_account_custom_errors,
    get_billing_account_custom_success,
    get_billing_account_responses,
    list_invoices_custom_errors,
    list_invoices_custom_success,
    list_invoices_responses,
    list_payment_methods_custom_errors,
    list_payment_methods_custom_success,
    list_payment_methods_responses,
    list_plans_custom_errors,
    list_plans_custom_success,
    list_plans_responses,
    set_default_payment_method_custom_errors,
    set_default_payment_method_custom_success,
    set_default_payment_method_responses,
    subscription_status_custom_errors,
    subscription_status_custom_success,
    subscription_status_responses,
)
from app.api.modules.v1.billing.schemas.billing_schema import (
    BillingAccountCreateRequest,
    BillingAccountResponse,
    BillingPlan,
    BillingPlanInfo,
    CheckoutSessionCreateRequest,
    CheckoutSessionResponse,
    InvoiceCreateRequest,
    InvoiceResponse,
    PaymentMethodCreateRequest,
    PaymentMethodResponse,
    SubscriptionCancelRequest,
    SubscriptionChangePlanRequest,
    SubscriptionStatusResponse,
)
from app.api.modules.v1.billing.service.billing_service import BillingService, get_billing_service
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_checkout_session as stripe_create_checkout_session,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_customer,
    resolve_stripe_price_id_for_product,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organizations/{organization_id}/billing",
    tags=["Billing"],
    dependencies=[Depends(require_billing_admin)],
)


@router.post(
    "/checkout",
    status_code=status.HTTP_200_OK,
    response_model=CheckoutSessionResponse,
    summary="Create Stripe Checkout session for subscription",
    responses=create_checkout_responses,
)
async def create_checkout_session(
    organization_id: UUID,
    payload: CheckoutSessionCreateRequest,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session for the organisation’s subscription.

    Args:
        organization_id (UUID):
            The UUID of the organisation creating a subscription.
        payload (CheckoutSessionCreateRequest):
            Request payload specifying plan (monthly/yearly) and optional metadata.
        current_user (Depends(require_billing_admin)):
            The authenticated user; must have billing permissions.
        db (AsyncSession, Depends(get_db)):
            The database session injected by FastAPI.

    Returns:
        dict: A standard API response containing:
            - `status_code`: HTTP status code.
            - `message`: A success message.
            - `data`: A `CheckoutSessionResponse` containing:
                - `checkout_url`: URL to redirect the user to Stripe Checkout.
                - `session_id`: The created Checkout session ID.

    Raises:
        HTTPException:
            - 400 if the plan is invalid.
            - 500 if Stripe customer creation fails or billing config is invalid.
        Exception:
            Any unexpected errors during checkout creation.
    """
    try:
        billing_service: BillingService = get_billing_service(db)

        account: BillingAccount = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            account = await billing_service.create_billing_account(
                organization_id=organization_id,
                currency="USD",
                customer_email=current_user.email,
                customer_name=current_user.name,
                metadata={"created_by": str(current_user.id)},
            )

        stripe_customer_id = account.stripe_customer_id
        if not stripe_customer_id:
            stripe_customer = await create_customer(
                email=current_user.email,
                name=current_user.name,
                metadata={"organization_id": str(organization_id)},
            )
            stripe_customer_id = stripe_customer.get("id")
            if not stripe_customer_id:
                logger.error("Stripe customer creation returned no id for org=%s", account.id)
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to create Stripe customer",
                )

            await billing_service.attach_stripe_customer(
                billing_account_id=account.id,
                stripe_customer_id=stripe_customer_id,
            )

        if payload.plan == BillingPlan.MONTHLY:
            price_id = settings.STRIPE_MONTHLY_PRICE_ID
        elif payload.plan == BillingPlan.YEARLY:
            price_id = settings.STRIPE_YEARLY_PRICE_ID
        else:
            logger.error("Unsupported billing plan: %s", payload.plan)
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Unsupported billing plan",
            )

        if not price_id:
            logger.error("Stripe price id not configured for plan=%s", payload.plan)
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Billing is not correctly configured. Please contact support.",
            )

        success_url = settings.STRIPE_CHECKOUT_SUCCESS_URL
        cancel_url = settings.STRIPE_CHECKOUT_CANCEL_URL

        base_metadata = {
            "organization_id": str(organization_id),
            "billing_account_id": str(account.id),
            "plan": payload.plan.value,
            "created_by": str(current_user.id),
        }

        if payload.metadata:
            base_metadata.update(payload.metadata)

        session = await stripe_create_checkout_session(
            success_url=str(success_url),
            cancel_url=str(cancel_url),
            customer_id=stripe_customer_id,
            mode="subscription",
            price_id=price_id,
            metadata=base_metadata,
        )

        response_payload = CheckoutSessionResponse(
            checkout_url=session["url"],
            session_id=session["id"],
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Checkout session created",
            data=response_payload,
        )

    except Exception as e:
        logger.exception("Failed to create Stripe checkout session: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create checkout session",
        )


create_checkout_session._custom_errors = create_checkout_custom_errors
create_checkout_session._custom_success = create_checkout_custom_success


@router.get(
    "/subscription",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusResponse,
    summary="Get current subscription status for organisation",
    responses=subscription_status_responses,
)
async def get_subscription_status(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        data = SubscriptionStatusResponse(
            billing_account_id=account.id,
            stripe_customer_id=account.stripe_customer_id,
            stripe_subscription_id=account.stripe_subscription_id,
            status=account.status,
            cancel_at_period_end=account.cancel_at_period_end or False,
            trial_starts_at=account.trial_starts_at,
            trial_ends_at=account.trial_ends_at,
            current_period_start=account.current_period_start,
            current_period_end=account.current_period_end,
            next_billing_at=account.next_billing_at,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Subscription status retrieved",
            data=data,
        )
    except Exception as e:
        logger.exception("Failed to get subscription status: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get subscription status",
        )


get_subscription_status._custom_errors = subscription_status_custom_errors
get_subscription_status._custom_success = subscription_status_custom_success


@router.post(
    "/subscription/change-plan",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusResponse,
    summary="Change subscription plan (monthly/yearly, etc)",
    responses=change_subscription_plan_responses,
)
async def change_subscription_plan(
    organization_id: UUID,
    payload: SubscriptionChangePlanRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        if not account.stripe_subscription_id:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No active subscription to change",
            )

        if payload.plan == BillingPlan.MONTHLY:
            new_price_id = settings.STRIPE_MONTHLY_PRICE_ID
        elif payload.plan == BillingPlan.YEARLY:
            new_price_id = settings.STRIPE_YEARLY_PRICE_ID
        else:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Unsupported billing plan",
            )

        if not new_price_id:
            logger.error("Stripe price id not configured for plan=%s", payload.plan)
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Billing is not correctly configured. Please contact support.",
            )

        updated = await billing_service.update_subscription_price_for_account(
            account=account,
            new_price_id=new_price_id,
        )

        data = SubscriptionStatusResponse(
            billing_account_id=updated.id,
            stripe_customer_id=updated.stripe_customer_id,
            stripe_subscription_id=updated.stripe_subscription_id,
            status=updated.status,
            cancel_at_period_end=updated.cancel_at_period_end or False,
            trial_starts_at=updated.trial_starts_at,
            trial_ends_at=updated.trial_ends_at,
            current_period_start=updated.current_period_start,
            current_period_end=updated.current_period_end,
            next_billing_at=updated.next_billing_at,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"Subscription plan changed to {payload.plan.value}",
            data=data,
        )
    except ValueError as ve:
        logger.warning("Change plan validation failed: %s", str(ve))
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(ve),
        )
    except Exception as e:
        logger.exception("Failed to change subscription plan: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to change subscription plan",
        )


change_subscription_plan._custom_errors = change_subscription_plan_custom_errors
change_subscription_plan._custom_success = change_subscription_plan_custom_success


@router.post(
    "/subscription/cancel",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusResponse,
    summary="Cancel subscription (stop renewal or immediate)",
    responses=cancel_subscription_responses,
)
async def cancel_subscription(
    organization_id: UUID,
    payload: SubscriptionCancelRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        if not account.stripe_subscription_id:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No active subscription to cancel",
            )

        updated = await billing_service.cancel_subscription_for_account(
            account=account,
            cancel_at_period_end=payload.cancel_at_period_end,
        )

        data = SubscriptionStatusResponse(
            billing_account_id=updated.id,
            stripe_customer_id=updated.stripe_customer_id,
            stripe_subscription_id=updated.stripe_subscription_id,
            status=updated.status,
            cancel_at_period_end=updated.cancel_at_period_end or False,
            trial_starts_at=updated.trial_starts_at,
            trial_ends_at=updated.trial_ends_at,
            current_period_start=updated.current_period_start,
            current_period_end=updated.current_period_end,
            next_billing_at=updated.next_billing_at,
        )

        msg = (
            "Subscription set to cancel at period end"
            if payload.cancel_at_period_end
            else "Subscription cancelled immediately"
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message=msg,
            data=data,
        )
    except ValueError as ve:
        logger.warning("Cancel subscription validation failed: %s", str(ve))
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(ve),
        )
    except Exception as e:
        logger.exception("Failed to cancel subscription: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to cancel subscription",
        )


cancel_subscription._custom_errors = cancel_subscription_custom_errors
cancel_subscription._custom_success = cancel_subscription_custom_success


@router.post(
    "/accounts",
    status_code=status.HTTP_201_CREATED,
    response_model=BillingAccountResponse,
    summary="Create billing account for your organisation",
    responses=create_billing_account_responses,
)
async def create_billing_account(
    organization_id: UUID,
    payload: BillingAccountCreateRequest,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a billing account for the authenticated user's organisation.

    Args:
        organization_id (UUID): The UUID of the organisation.
        payload (BillingAccountCreateRequest): Request payload containing account
            creation details.
        current_user (Depends(require_billing_admin)): The authenticated user object.
        db (AsyncSession, Depends(get_db)): Asynchronous database session injected
            by FastAPI dependencies.

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the created billing account

    Raises:
        ValueError: If validation of the input payload fails.
        Exception: For unexpected errors encountered while creating the billing account
    """
    try:
        billing_service: BillingService = get_billing_service(db)

        account = await billing_service.create_billing_account(
            organization_id=organization_id,
            currency=(payload.currency or "USD"),
            customer_email=current_user.email,
            customer_name=current_user.name,
            metadata={"created_by": str(current_user.id)},
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Billing account created",
            data=BillingAccountResponse.model_validate(account.model_dump()),
        )
    except ValueError as e:
        logger.warning("Create billing account validation failed: %s", str(e))
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating billing account: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create billing account",
        )


create_billing_account._custom_errors = create_billing_account_custom_errors
create_billing_account._custom_success = create_billing_account_custom_success


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=BillingAccountResponse,
    summary="Get billing account for your organisation",
    responses=get_billing_account_responses,
)
async def get_billing_account(
    organization_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the billing account for the authenticated user's organisation.

    Args:
        organization_id (UUID): The UUID of the organisation.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the retrieved billing account

    Raises:
        Exception: For unexpected errors encountered while fetching the billing account
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found for organisation",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Billing account retrieved",
            data=BillingAccountResponse.model_validate(account.model_dump()),
        )
    except Exception as e:
        logger.exception("Failed to fetch billing account: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch billing account",
        )


get_billing_account._custom_errors = get_billing_account_custom_errors
get_billing_account._custom_success = get_billing_account_custom_success


@router.post(
    "/payment-methods",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentMethodResponse,
    summary="Add a payment method (metadata only)",
    responses=add_payment_method_responses,
)
async def add_payment_method(
    organization_id: UUID,
    payload: PaymentMethodCreateRequest,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a non-sensitive payment method record to the billing account for the caller's organisation.

    Args:
        organization_id (UUID): The UUID of the organisation.
        payload (PaymentMethodCreateRequest): The payment method details provided by the client.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`.
            On success `data` will be the added payment method.

    Raises:
        Exception: For unexpected errors encountered while adding the payment method.
    """
    try:
        billing_service: BillingService = get_billing_service(db)

        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Billing account not found"
            )

        pm = await billing_service.add_payment_method(
            billing_account_id=account.id,
            stripe_payment_method_id=payload.stripe_payment_method_id,
            card_brand=payload.card_brand,
            last4=payload.last4,
            exp_month=payload.exp_month,
            exp_year=payload.exp_year,
            is_default=payload.is_default,
            metadata={"created_by": str(current_user.id)},
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Payment method added",
            data=PaymentMethodResponse.model_validate(pm.model_dump()),
        )
    except ValueError as e:
        logger.warning("Failed to add payment method: %s", str(e))
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))
    except Exception as e:
        logger.exception("Unexpected error adding payment method: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to add payment method",
        )


add_payment_method._custom_errors = add_payment_method_custom_errors
add_payment_method._custom_success = add_payment_method_custom_success


@router.get(
    "/payment-methods",
    status_code=status.HTTP_200_OK,
    response_model=List[PaymentMethodResponse],
    summary="List payment methods for account",
    responses=list_payment_methods_responses,
)
async def list_payment_methods(
    organization_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all payment methods associated with the caller's billing account.
    Args:
        organization_id (UUID): The UUID of the organisation.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the retrieved billing account

    Raises:
        Exception: For unexpected errors encountered while fetching the billing account.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Billing account not found"
            )

        pms = await billing_service.list_payment_methods(account.id)
        data = [PaymentMethodResponse.model_validate(pm.model_dump()) for pm in pms]
        return success_response(
            status_code=status.HTTP_200_OK, message="Payment methods retrieved", data=data
        )
    except Exception as e:
        logger.exception("Failed to list payment methods: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list payment methods",
        )


list_payment_methods._custom_errors = list_payment_methods_custom_errors
list_payment_methods._custom_success = list_payment_methods_custom_success


@router.post(
    "/payment-methods/{payment_method_id}/default",
    status_code=status.HTTP_200_OK,
    response_model=PaymentMethodResponse,
    summary="Set default payment method",
    responses=set_default_payment_method_responses,
)
async def set_default_payment_method(
    organization_id: UUID,
    payment_method_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Set a payment method as default for the caller's billing account.
    Args:
        organization_id (UUID): The UUID of the organisation.
        payment_method_id (UUID): The ID of the payment method to set as default.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the updated payment method.

    Raises:
        ValueError: If the payment method does not belong to the caller's billing account.
        Exception: For unexpected errors encountered while setting the default payment method.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Billing account not found"
            )

        pm = await billing_service.set_default_payment_method(
            billing_account_id=account.id, payment_method_id=payment_method_id
        )
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Default payment method set",
            data=PaymentMethodResponse.model_validate(pm.model_dump()),
        )
    except ValueError as ve:
        logger.warning("Invalid request to set default payment method: %s", str(ve))
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(ve))
    except Exception as e:
        logger.exception("Failed to set default payment method: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to set default payment method",
        )


set_default_payment_method._custom_errors = set_default_payment_method_custom_errors
set_default_payment_method._custom_success = set_default_payment_method_custom_success


@router.delete(
    "/payment-methods/{payment_method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment method",
    responses=delete_payment_method_responses,
)
async def delete_payment_method(
    organization_id: UUID,
    payment_method_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a payment method record.

    Args:
        organization_id (UUID): The UUID of the organisation
        payment_method_id (UUID): The ID of the payment method to delete.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will indicate deletion status.

    Raises:
        ValueError: If the payment method does not belong to the caller's billing account.
        Exception: For unexpected errors encountered while deleting the payment method.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        success = await billing_service.delete_payment_method(payment_method_id=payment_method_id)
        if not success:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Payment method not found"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.exception("Failed to delete payment method: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete payment method",
        )


delete_payment_method._custom_errors = delete_payment_method_custom_errors
delete_payment_method._custom_success = delete_payment_method_custom_success


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    response_model=List[BillingPlanInfo],
    summary="List available subscription plans",
    responses=list_plans_responses,
)
async def list_plans(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Return the available subscription plans with pricing and Stripe metadata.
    """
    plans: List[BillingPlanInfo] = [
        BillingPlanInfo(
            code=BillingPlan.MONTHLY,
            label="Pro Monthly",
            price_id=settings.STRIPE_MONTHLY_PRICE_ID,
            product_id=settings.STRIPE_MONTHLY_PRODUCT_ID,
            interval="month",
            currency="USD",
            amount=settings.MONTHLY_PRICE,
        ),
        BillingPlanInfo(
            code=BillingPlan.YEARLY,
            label="Pro Yearly",
            price_id=settings.STRIPE_YEARLY_PRICE_ID,
            product_id=settings.STRIPE_YEARLY_PRODUCT_ID,
            interval="year",
            currency="USD",
            amount=settings.YEARLY_PRICE,
        ),
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Plans retrieved",
        data=plans,
    )


list_plans._custom_errors = list_plans_custom_errors
list_plans._custom_success = list_plans_custom_success


@router.post(
    "/invoices",
    status_code=status.HTTP_201_CREATED,
    response_model=InvoiceResponse,
    summary="Create an invoice (Stripe + local history)",
    responses=create_invoice_record_responses,
)
async def create_invoice_record(
    organization_id: UUID,
    payload: InvoiceCreateRequest,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create an invoice for one of our predefined products/plans.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        stripe_price_id = await resolve_stripe_price_id_for_product(payload.product_id)

        invoice = await billing_service.create_stripe_and_local_invoice(
            billing_account_id=account.id,
            stripe_price_id=stripe_price_id,
            quantity=payload.quantity,
            description=payload.description,
            metadata={"organization_id": str(organization_id)},
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Invoice record created",
            data=InvoiceResponse.model_validate(invoice.model_dump()),
        )
    except HTTPException as e:
        logger.exception("Failed to create invoice record (HTTP): %s", str(e))
        return error_response(status_code=e.status_code, message=e.detail)
    except Exception as e:
        logger.exception("Failed to create invoice record: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create invoice record",
        )


create_invoice_record._custom_errors = create_invoice_record_custom_errors
create_invoice_record._custom_success = create_invoice_record_custom_success


@router.get(
    "/invoices",
    status_code=status.HTTP_200_OK,
    response_model=List[InvoiceResponse],
    summary="List invoices for the caller's billing account",
    responses=list_invoices_responses,
)
async def list_invoices(
    organization_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all invoices for the caller's billing account (newest first).

    Args:
        organization_id (UUID): The UUID of the organisation.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the list of invoices.

    Raises:
        Exception: For unexpected errors encountered while fetching the invoices.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Billing account not found"
            )

        invoices = await billing_service.get_invoices_for_account(account.id)
        data = [InvoiceResponse.model_validate(inv.model_dump()) for inv in invoices]
        return success_response(
            status_code=status.HTTP_200_OK, message="Invoices retrieved", data=data
        )
    except Exception as e:
        logger.exception("Failed to list invoices: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Failed to list invoices"
        )


list_invoices._custom_errors = list_invoices_custom_errors
list_invoices._custom_success = list_invoices_custom_success
