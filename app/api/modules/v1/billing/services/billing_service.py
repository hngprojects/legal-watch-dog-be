import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.logger import setup_logging
from app.api.modules.v1.billing.models import (
    BillingAccount,
    InvoiceHistory,
    PaymentMethod,
    Subscription,
)
from app.api.modules.v1.billing.schemas.responses import (
    BillingMetricsResponse,
    BillingSummaryResponse,
    CheckoutSessionResponse,
    InvoiceResponse,
    NextInvoiceResponse,
    PaymentMethodResponse,
    PortalSessionResponse,
    SubscriptionResponse,
)
from app.api.modules.v1.billing.services.stripe_client import StripeClient

setup_logging()
logger = logging.getLogger(__name__)


class BillingService:
    """
    Async business logic layer for billing operations.
    Orchestrates Stripe API calls and database operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.stripe_client = StripeClient()

    # BILLING ACCOUNT OPERATIONS

    async def get_or_create_billing_account(
        self,
        organization_id: UUID,
        user_email: str,
        organization_name: Optional[str] = None,
    ) -> BillingAccount:
        """Get existing billing account or create new one (async)"""
        logger.info(
            "Getting or creating billing account",
            extra={"organization_id": str(organization_id), "user_email": user_email},
        )

        # Check if billing account already exists
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.exec(statement)
        existing_account = result.scalar_one_or_none()

        if existing_account:
            logger.info(
                "Billing account already exists",
                extra={
                    "billing_account_id": str(existing_account.id),
                    "organization_id": str(organization_id),
                },
            )
            return existing_account

        # Create new Stripe customer
        try:
            stripe_customer = await self.stripe_client.create_customer(
                email=user_email,
                name=organization_name,
                metadata={"organization_id": str(organization_id)},
            )
        except Exception as e:
            logger.error(
                "Failed to create Stripe customer",
                exc_info=True,
                extra={"organization_id": str(organization_id), "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create billing account",
            )

        # Create billing account with trial
        trial_ends_at = datetime.now(tz=timezone.utc) + timedelta(days=settings.TRIAL_DURATION_DAYS)

        billing_account = BillingAccount(
            organization_id=organization_id,
            stripe_customer_id=stripe_customer.id,
            status="trialing",
            trial_ends_at=trial_ends_at,
            default_pm_id=None,
            default_pm_brand=None,
            default_pm_exp_month=None,
            default_pm_exp_year=None,
            current_subscription_id=None,
        )

        self.db.add(billing_account)
        await self.db.commit()
        await self.db.refresh(billing_account)

        logger.info(
            "Billing account created successfully",
            extra={
                "billing_account_id": str(billing_account.id),
                "organization_id": str(organization_id),
                "stripe_customer_id": stripe_customer.id,
                "trial_ends_at": trial_ends_at.isoformat(),
            },
        )

        return billing_account

    async def get_billing_summary(self, organization_id: UUID) -> BillingSummaryResponse:
        """Get complete billing summary (async)"""
        logger.info("Fetching billing summary", extra={"organization_id": str(organization_id)})

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            logger.error(
                "Billing account not found",
                extra={"organization_id": str(organization_id)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        # Calculate trial information
        trial_days_remaining = 0
        is_trial_expired = False

        if billing_account.trial_ends_at:
            now = datetime.utcnow()
            if now < billing_account.trial_ends_at:
                trial_days_remaining = (billing_account.trial_ends_at - now).days
            else:
                is_trial_expired = True

        # Get current subscription
        current_subscription = None
        current_period_end = None
        has_active_subscription = False

        if billing_account.current_subscription_id:
            sub_statement = select(Subscription).where(
                Subscription.id == billing_account.current_subscription_id
            )
            sub_result = await self.db.execute(sub_statement)
            subscription = sub_result.scalar_one_or_none()

            if subscription and subscription.status in ["active", "trialing"]:
                has_active_subscription = True
                current_subscription = SubscriptionResponse.model_validate(subscription)
                current_period_end = subscription.current_period_end

        # Get payment methods
        pm_statement = select(PaymentMethod).where(
            PaymentMethod.billing_account_id == billing_account.id
        )
        pm_result = await self.db.execute(pm_statement)
        payment_methods = pm_result.scalars().all()
        payment_methods_response = [
            PaymentMethodResponse.model_validate(pm) for pm in payment_methods
        ]

        # Get recent invoices
        invoice_statement = (
            select(InvoiceHistory)
            .where(InvoiceHistory.billing_account_id == billing_account.id)
            .order_by(InvoiceHistory.invoice_date.desc())
            .limit(5)
        )
        invoice_result = await self.db.execute(invoice_statement)
        invoices = invoice_result.scalars().all()
        invoices_response = [InvoiceResponse.model_validate(inv) for inv in invoices]

        # Get next invoice from Stripe
        next_invoice = None
        if billing_account.stripe_customer_id and has_active_subscription:
            try:
                upcoming_invoice = await self.stripe_client.get_upcoming_invoice(
                    customer_id=billing_account.stripe_customer_id,
                    subscription_id=(
                        current_subscription.stripe_subscription_id
                        if current_subscription
                        else None
                    ),
                )

                if upcoming_invoice:
                    next_invoice = NextInvoiceResponse(
                        amount_due=upcoming_invoice.amount_due,
                        currency=upcoming_invoice.currency,
                        billing_date=datetime.fromtimestamp(upcoming_invoice.period_end),
                        line_items=[
                            {
                                "description": item.description,
                                "amount": item.amount,
                                "quantity": item.quantity,
                            }
                            for item in upcoming_invoice.lines.data
                        ],
                    )
            except Exception as e:
                logger.warning(
                    "Failed to fetch upcoming invoice",
                    extra={
                        "billing_account_id": str(billing_account.id),
                        "error": str(e),
                    },
                )

        # Determine billing status
        billing_status = self._determine_billing_status(
            billing_account, is_trial_expired, has_active_subscription
        )

        summary = BillingSummaryResponse(
            billing_account_id=billing_account.id,
            organization_id=billing_account.organization_id,
            stripe_customer_id=billing_account.stripe_customer_id,
            status=billing_status,
            trial_ends_at=billing_account.trial_ends_at,
            trial_days_remaining=trial_days_remaining,
            is_trial_expired=is_trial_expired,
            has_active_subscription=has_active_subscription,
            current_subscription=current_subscription,
            current_period_end=current_period_end,
            next_invoice=next_invoice,
            payment_methods=payment_methods_response,
            recent_invoices=invoices_response,
            created_at=billing_account.created_at,
            blocked_at=billing_account.blocked_at,
        )

        logger.info(
            "Billing summary retrieved successfully",
            extra={
                "billing_account_id": str(billing_account.id),
                "status": billing_status,
                "has_active_subscription": has_active_subscription,
            },
        )

        return summary

    def _determine_billing_status(
        self,
        billing_account: BillingAccount,
        is_trial_expired: bool,
        has_active_subscription: bool,
    ) -> str:
        """Determine the current billing status"""
        if billing_account.status == "blocked":
            return "blocked"

        if not is_trial_expired and not has_active_subscription:
            return "trialing"

        if has_active_subscription:
            if billing_account.status == "past_due":
                return "past_due"
            return "active"

        if is_trial_expired and not has_active_subscription:
            return "blocked"

        if billing_account.status == "canceled":
            return "canceled"

        return billing_account.status

    # CHECKOUT & PORTAL OPERATIONS

    async def create_checkout_session(
        self,
        organization_id: UUID,
        plan: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> CheckoutSessionResponse:
        """Create Stripe Checkout session (async)"""
        logger.info(
            "Creating checkout session",
            extra={"organization_id": str(organization_id), "plan": plan},
        )

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        if not billing_account.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe customer not configured",
            )

        # Determine price ID
        price_id = (
            settings.STRIPE_MONTHLY_PRICE_ID
            if plan == "monthly"
            else settings.STRIPE_YEARLY_PRICE_ID
        )

        # Set default URLs if not provided
        if not success_url:
            success_url = (
                f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
            )
        if not cancel_url:
            cancel_url = f"{settings.FRONTEND_URL}/billing/cancel"

        # Create checkout session
        try:
            session = await self.stripe_client.create_checkout_session(
                customer_id=billing_account.stripe_customer_id,
                price_id=price_id,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "organization_id": str(organization_id),
                    "billing_account_id": str(billing_account.id),
                    "plan": plan,
                },
                trial_period_days=None,
            )

            logger.info(
                "Checkout session created successfully",
                extra={
                    "session_id": session.id,
                    "billing_account_id": str(billing_account.id),
                },
            )

            return CheckoutSessionResponse(checkout_url=session.url, session_id=session.id)

        except Exception as e:
            logger.error(
                "Failed to create checkout session",
                exc_info=True,
                extra={"billing_account_id": str(billing_account.id), "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create checkout session",
            )

    async def create_portal_session(
        self, organization_id: UUID, return_url: Optional[str] = None
    ) -> PortalSessionResponse:
        """Create Stripe Portal session (async)"""
        logger.info("Creating portal session", extra={"organization_id": str(organization_id)})

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        if not billing_account.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe customer not configured",
            )

        # Set default return URL
        if not return_url:
            return_url = f"{settings.FRONTEND_URL}/billing"

        # Create portal session
        try:
            session = await self.stripe_client.create_portal_session(
                customer_id=billing_account.stripe_customer_id, return_url=return_url
            )

            logger.info(
                "Portal session created successfully",
                extra={
                    "session_id": session.id,
                    "billing_account_id": str(billing_account.id),
                },
            )

            return PortalSessionResponse(portal_url=session.url)

        except Exception as e:
            logger.error(
                "Failed to create portal session",
                exc_info=True,
                extra={"billing_account_id": str(billing_account.id), "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create portal session",
            )

    #  PAYMENT METHOD OPERATIONS

    async def attach_payment_method(
        self, organization_id: UUID, payment_method_id: str, set_as_default: bool = True
    ) -> PaymentMethodResponse:
        """Attach payment method (async)"""
        logger.info(
            "Attaching payment method",
            extra={
                "organization_id": str(organization_id),
                "payment_method_id": payment_method_id,
                "set_as_default": set_as_default,
            },
        )

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        if not billing_account.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe customer not configured",
            )

        # Check if payment method already exists
        pm_statement = select(PaymentMethod).where(
            PaymentMethod.billing_account_id == billing_account.id,
            PaymentMethod.stripe_pm_id == payment_method_id,
        )
        pm_result = await self.db.execute(pm_statement)
        existing_pm = pm_result.scalar_one_or_none()

        if existing_pm:
            logger.info(
                "Payment method already attached",
                extra={"payment_method_id": payment_method_id},
            )
            return PaymentMethodResponse.model_validate(existing_pm)

        # Attach to Stripe customer
        try:
            stripe_pm = await self.stripe_client.attach_payment_method(
                payment_method_id=payment_method_id,
                customer_id=billing_account.stripe_customer_id,
            )

            # Set as default if requested
            if set_as_default:
                await self.stripe_client.set_default_payment_method(
                    customer_id=billing_account.stripe_customer_id,
                    payment_method_id=payment_method_id,
                )

                # Update all existing payment methods to non-default
                update_statement = select(PaymentMethod).where(
                    PaymentMethod.billing_account_id == billing_account.id
                )
                update_result = await self.db.execute(update_statement)
                existing_pms = update_result.scalars().all()
                for pm in existing_pms:
                    pm.is_default = False

            # Save to database
            payment_method = PaymentMethod(
                billing_account_id=billing_account.id,
                stripe_pm_id=stripe_pm.id,
                brand=stripe_pm.card.brand,
                last4=stripe_pm.card.last4,
                exp_month=stripe_pm.card.exp_month,
                exp_year=stripe_pm.card.exp_year,
                is_default=set_as_default,
            )

            self.db.add(payment_method)
            await self.db.commit()
            await self.db.refresh(payment_method)

            # Update billing account default PM info
            if set_as_default:
                billing_account.default_pm_id = stripe_pm.id
                billing_account.default_pm_brand = stripe_pm.card.brand
                billing_account.default_pm_exp_month = stripe_pm.card.exp_month
                billing_account.default_pm_exp_year = stripe_pm.card.exp_year
                await self.db.commit()

            logger.info(
                "Payment method attached successfully",
                extra={
                    "payment_method_id": payment_method_id,
                    "billing_account_id": str(billing_account.id),
                },
            )

            return PaymentMethodResponse.model_validate(payment_method)

        except Exception as e:
            logger.error(
                "Failed to attach payment method",
                exc_info=True,
                extra={"payment_method_i": payment_method_id, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to attach payment method",
            )

    #  SUBSCRIPTION OPERATIONS

    async def update_subscription(
        self, organization_id: UUID, new_plan: str, prorate: bool = True
    ) -> SubscriptionResponse:
        """Update subscription (async)"""
        logger.info(
            "Updating subscription",
            extra={
                "organization_id": str(organization_id),
                "new_plan": new_plan,
                "prorate": prorate,
            },
        )

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        if not billing_account.current_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription to update",
            )

        # Get current subscription
        sub_statement = select(Subscription).where(
            Subscription.id == billing_account.current_subscription_id
        )
        sub_result = await self.db.execute(sub_statement)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
            )

        # Check if already on the requested plan
        if subscription.plan == new_plan:
            logger.info(
                "Subscription already on requested plan",
                extra={"subscription_id": str(subscription.id), "plan": new_plan},
            )
            return SubscriptionResponse.model_validate(subscription)

        # Determine new price ID
        new_price_id = (
            settings.STRIPE_MONTHLY_PRICE_ID
            if new_plan == "monthly"
            else settings.STRIPE_YEARLY_PRICE_ID
        )

        # Update in Stripe
        try:
            stripe_subscription = await self.stripe_client.update_subscription(
                subscription_id=subscription.stripe_subscription_id,
                new_price_id=new_price_id,
                prorate=prorate,
            )

            # Update in database
            subscription.plan = new_plan
            subscription.status = stripe_subscription.status
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end
            )

            await self.db.commit()
            await self.db.refresh(subscription)

            logger.info(
                "Subscription updated successfully",
                extra={"subscription_id": str(subscription.id), "new_plan": new_plan},
            )

            return SubscriptionResponse.model_validate(subscription)

        except Exception as e:
            logger.error(
                "Failed to update subscription",
                exc_info=True,
                extra={"subscription_id": str(subscription.id), "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update subscription",
            )

    async def cancel_subscription(
        self,
        organization_id: UUID,
        cancel_at_period_end: bool = True,
        cancellation_reason: Optional[str] = None,
    ) -> SubscriptionResponse:
        """Cancel subscription (async)"""
        logger.info(
            "Canceling subscription",
            extra={
                "organization_id": str(organization_id),
                "cancel_at_period_end": cancel_at_period_end,
                "reason": cancellation_reason,
            },
        )

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        if not billing_account.current_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active subscription to cancel",
            )

        # Get subscription
        sub_statement = select(Subscription).where(
            Subscription.id == billing_account.current_subscription_id
        )
        sub_result = await self.db.execute(sub_statement)
        subscription = sub_result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
            )

        # Check if already canceled
        if subscription.status == "canceled":
            logger.info(
                "Subscription already canceled",
                extra={"subscription_id": str(subscription.id)},
            )
            return SubscriptionResponse.model_validate(subscription)

        # Cancel in Stripe
        try:
            stripe_subscription = await self.stripe_client.cancel_subscription(
                subscription_id=subscription.stripe_subscription_id,
                cancel_at_period_end=cancel_at_period_end,
            )

            # Log Stripe info
            logger.info(
                "Canceled subscription in Stripe",
                extra={
                    "stripe_subscription_id": stripe_subscription.get("id"),
                    "status": stripe_subscription.get("status"),
                },
            )

        except Exception as e:
            logger.error(
                "Failed to cancel subscription in Stripe",
                exc_info=True,
                extra={"subscription_id": str(subscription.id), "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel subscription in Stripe",
            )

        # Update subscription in the database
        subscription.cancel_at_period_end = cancel_at_period_end
        subscription.canceled_at = datetime.utcnow()

        if not cancel_at_period_end:
            subscription.status = "canceled"
            subscription.ended_at = datetime.utcnow()
            billing_account.status = "canceled"

        await self.db.commit()
        await self.db.refresh(subscription)

        logger.info(
            "Subscription canceled successfully",
            extra={
                "subscription_id": str(subscription.id),
                "cancel_at_period_end": cancel_at_period_end,
            },
        )

        return SubscriptionResponse.model_validate(subscription)

    #  INVOICE OPERATIONS

    async def list_invoices(
        self, organization_id: UUID, limit: int = 10, offset: int = 0
    ) -> List[InvoiceResponse]:
        """List invoices (async)"""
        logger.info(
            "Listing invoices",
            extra={
                "organization_id": str(organization_id),
                "limit": limit,
                "offset": offset,
            },
        )

        # Get billing account
        statement = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        result = await self.db.execute(statement)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Billing account not found",
            )

        # Sync invoices from Stripe if customer exists
        if billing_account.stripe_customer_id:
            try:
                stripe_invoices = await self.stripe_client.list_invoices(
                    customer_id=billing_account.stripe_customer_id, limit=limit
                )

                # Sync to database
                for stripe_invoice in stripe_invoices:
                    await self._sync_invoice_to_db(billing_account.id, stripe_invoice)

            except Exception as e:
                logger.warning(
                    "Failed to sync invoices from Stripe",
                    extra={
                        "billing_account_id": str(billing_account.id),
                        "error": str(e),
                    },
                )

        # Fetch from database
        invoice_statement = (
            select(InvoiceHistory)
            .where(InvoiceHistory.billing_account_id == billing_account.id)
            .order_by(InvoiceHistory.invoice_date.desc())
            .offset(offset)
            .limit(limit)
        )

        invoice_result = await self.db.execute(invoice_statement)
        invoices = invoice_result.scalars().all()

        logger.info(
            "Invoices retrieved successfully",
            extra={
                "billing_account_id": str(billing_account.id),
                "count": len(invoices),
            },
        )

        return [InvoiceResponse.model_validate(inv) for inv in invoices]

    async def get_invoice_pdf_url(self, invoice_id: UUID) -> str:
        """Get invoice PDF URL (async)"""
        logger.info("Getting invoice PDF URL", extra={"invoice_id": str(invoice_id)})

        # Get invoice
        statement = select(InvoiceHistory).where(InvoiceHistory.id == invoice_id)
        result = await self.db.execute(statement)
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

        # Try database first
        if invoice.invoice_pdf_url:
            return invoice.invoice_pdf_url

        # Fetch from Stripe
        try:
            pdf_url = await self.stripe_client.get_invoice_pdf(invoice_id=invoice.stripe_invoice_id)

            if pdf_url:
                # Update database
                invoice.invoice_pdf_url = pdf_url
                await self.db.commit()

                return pdf_url
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invoice PDF not available",
                )

        except Exception as e:
            logger.error(
                "Failed to get invoice PDF",
                exc_info=True,
                extra={"invoice_id": str(invoice_id), "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve invoice PDF",
            )

    async def _sync_invoice_to_db(
        self, billing_account_id: UUID, stripe_invoice: Any
    ) -> InvoiceHistory:
        """Sync Stripe invoice to database (async)"""
        # Check if invoice already exists
        statement = select(InvoiceHistory).where(
            InvoiceHistory.stripe_invoice_id == stripe_invoice.id
        )
        result = await self.db.execute(statement)
        existing_invoice = result.scalar_one_or_none()

        if existing_invoice:
            return existing_invoice

        # Create new invoice record
        invoice = InvoiceHistory(
            billing_account_id=billing_account_id,
            invoice_id=None,
            stripe_invoice_id=stripe_invoice.id,
            amount=Decimal(stripe_invoice.amount_paid) / 100,
            currency=stripe_invoice.currency,
            status=stripe_invoice.status,
            paid=stripe_invoice.paid,
            invoice_pdf_url=stripe_invoice.invoice_pdf,
            hosted_invoice_url=stripe_invoice.hosted_invoice_url,
            invoice_date=datetime.fromtimestamp(stripe_invoice.created),
            reason=None,
        )

        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)

        logger.debug(
            "Invoice synced to database",
            extra={
                "invoice_id": str(invoice.id),
                "stripe_invoice_id": stripe_invoice.id,
            },
        )

        return invoice

    # ADMIN OPERATIONS

    async def get_billing_metrics(self) -> BillingMetricsResponse:
        """Get billing metrics (async)"""
        logger.info("Fetching billing metrics")

        # Total accounts
        total_accounts_stmt = select(func.count(BillingAccount.id))
        total_accounts_result = await self.db.execute(total_accounts_stmt)
        total_accounts = total_accounts_result.scalar()

        # Active subscriptions
        active_subs_stmt = select(func.count(Subscription.id)).where(
            Subscription.status.in_(["active", "trialing"])
        )
        active_subs_result = await self.db.execute(active_subs_stmt)
        active_subscriptions = active_subs_result.scalar()

        # Trial accounts
        trial_accounts_stmt = select(func.count(BillingAccount.id)).where(
            BillingAccount.status == "trialing"
        )
        trial_accounts_result = await self.db.execute(trial_accounts_stmt)
        trial_accounts = trial_accounts_result.scalar()

        # Past due accounts
        past_due_stmt = select(func.count(BillingAccount.id)).where(
            BillingAccount.status == "past_due"
        )
        past_due_result = await self.db.execute(past_due_stmt)
        past_due_accounts = past_due_result.scalar()

        # Blocked accounts
        blocked_stmt = select(func.count(BillingAccount.id)).where(
            BillingAccount.status == "blocked"
        )
        blocked_result = await self.db.execute(blocked_stmt)
        blocked_accounts = blocked_result.scalar()

        # Calculate MRR and ARR
        monthly_subs_stmt = select(func.count(Subscription.id)).where(
            Subscription.plan == "monthly", Subscription.status == "active"
        )
        monthly_subs_result = await self.db.execute(monthly_subs_stmt)
        monthly_subs = monthly_subs_result.scalar()

        yearly_subs_stmt = select(func.count(Subscription.id)).where(
            Subscription.plan == "yearly", Subscription.status == "active"
        )
        yearly_subs_result = await self.db.execute(yearly_subs_stmt)
        yearly_subs = yearly_subs_result.scalar()

        monthly_recurring_revenue = Decimal(monthly_subs * 100)
        annual_recurring_revenue = Decimal(yearly_subs * 1200)
        total_arr = monthly_recurring_revenue * 12 + annual_recurring_revenue

        # ARPU
        average_revenue_per_user = None
        if total_accounts > 0:
            average_revenue_per_user = (
                monthly_recurring_revenue + annual_recurring_revenue / 12
            ) / total_accounts

        metrics = BillingMetricsResponse(
            total_accounts=total_accounts,
            active_subscriptions=active_subscriptions,
            trial_accounts=trial_accounts,
            past_due_accounts=past_due_accounts,
            blocked_accounts=blocked_accounts,
            monthly_recurring_revenue=monthly_recurring_revenue,
            annual_recurring_revenue=total_arr,
            churn_rate=None,
            average_revenue_per_user=average_revenue_per_user,
        )

        logger.info(
            "Billing metrics calculated",
            extra={
                "total_accounts": total_accounts,
                "active_subscriptions": active_subscriptions,
            },
        )

        return metrics

    # HELPER METHODS

    def validate_organization_ownership(
        self, organization_id: UUID, current_user_org_id: UUID
    ) -> None:
        """Validate organization ownership"""
        if organization_id != current_user_org_id:
            logger.warning(
                "Organization access denied",
                extra={
                    "requested_org_id": str(organization_id),
                    "user_org_id": str(current_user_org_id),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this organization's billing",
            )
