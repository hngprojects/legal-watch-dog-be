import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.modules.v1.billing.models.billing_account import BillingAccount, BillingStatus
from app.api.modules.v1.billing.models.invoice_history import InvoiceHistory, InvoiceStatus
from app.api.modules.v1.billing.models.payment_method import PaymentMethod
from app.api.modules.v1.billing.stripe.errors import SubscriptionAlreadyCanceledError
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    attach_payment_method as stripe_attach_payment_method,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    cancel_subscription as stripe_cancel_subscription,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_customer as stripe_create_customer,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_invoice_for_customer_with_price_id as stripe_create_invoice_for_customer_with_price_id,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    detach_payment_method as stripe_detach_payment_method,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    retrieve_subscription as stripe_retrieve_subscription,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    update_subscription_price as stripe_update_subscription_price,
)

logger = logging.getLogger(__name__)

TRIAL_DURATION_DAYS = settings.TRIAL_DURATION_DAYS
DEFAULT_CURRENCY = "USD"


class BillingService:
    """
    Service layer for billing operations.

    This class encapsulates domain logic and database interactions for billing
    accounts, payment methods and invoices.
    """

    def __init__(self, db: AsyncSession):
        """Create a BillingService.

        Args:
            db: AsyncSession instance (dependency-injected) used for DB access.
        """
        self.db = db

    async def is_org_allowed_usage(
        self, organization_id: UUID
    ) -> Tuple[bool, BillingStatus | None]:
        """
        Determine whether the given organisation is allowed to use the product
        right now, based on its BillingAccount and status.

        Returns:
            (allowed, effective_status)
        """
        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        account: BillingAccount | None = await self.db.scalar(stmt)

        if not account:
            return False, None

        now = datetime.now(timezone.utc)

        effective_status: BillingStatus = account.status

        if effective_status == BillingStatus.TRIALING:
            if account.trial_ends_at and now > account.trial_ends_at:
                effective_status = BillingStatus.UNPAID

        if effective_status == BillingStatus.ACTIVE:
            if account.current_period_end and now > account.current_period_end:
                if account.cancel_at_period_end:
                    effective_status = BillingStatus.CANCELLED
                else:
                    effective_status = BillingStatus.PAST_DUE

        allowed = False

        if effective_status in (BillingStatus.TRIALING, BillingStatus.ACTIVE):
            allowed = True

        else:
            allowed = False

        return allowed, effective_status

    async def create_billing_account(
        self,
        organization_id: UUID,
        currency: str = DEFAULT_CURRENCY,
        initial_status: BillingStatus = BillingStatus.TRIALING,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> BillingAccount:
        """
        Create a billing account for an organisation.

        Args:
            organization_id (UUID): The ID of the organization to create the billing account for.
            currency (str, optional): ISO currency code for the account. Defaults to "USD".
            initial_status (BillingStatus, optional): Initial billing status for the account.
                Defaults to BillingStatus.TRIALING.
            metadata (Optional[Dict[str, Any]], optional): Optional metadata to attach.
            customer_email (Optional[str]): Optional email to use to create Stripe Customer.
            customer_name (Optional[str]): Optional name for Stripe Customer.

        Raises:
            ValueError: If a billing account already exists for the given organization_id.
            Exception: If a database operation (flush/refresh/commit) fails;
                the transaction will be rolled back and the original exception re-raised.

        Returns:
            BillingAccount: persisted billing account object

        """
        currency = (currency or DEFAULT_CURRENCY).upper()

        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        existing = await self.db.scalar(stmt)
        if existing:
            raise ValueError("Billing account already exists for this organisation")

        stripe_customer_id: Optional[str] = None
        if customer_email:
            stripe_customer = await stripe_create_customer(
                email=customer_email, name=customer_name, metadata=metadata or {}
            )
            stripe_customer_id = stripe_customer.get("id")
            if not stripe_customer_id:
                logger.error("Stripe customer creation returned no id: %s", stripe_customer)
                raise Exception("Stripe customer creation failed")

            logger.info(
                "Stripe customer created: %s for org=%s", stripe_customer_id, organization_id
            )

        trial_starts_at = datetime.now(timezone.utc)
        trial_ends_at = trial_starts_at + timedelta(days=TRIAL_DURATION_DAYS)

        account = BillingAccount(
            organization_id=organization_id,
            stripe_customer_id=stripe_customer_id,
            status=initial_status,
            trial_starts_at=trial_starts_at,
            trial_ends_at=trial_ends_at,
            currency=currency,
            metadata_=(metadata or {}),
        )

        try:
            self.db.add(account)
            await self.db.flush()
            await self.db.refresh(account)
            await self.db.commit()
            logger.info("Created billing account (%s) for org=%s", account.id, organization_id)
            return account
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create billing account for org=%s: %s", organization_id, exc
            )
            raise

    async def get_billing_account_by_org(self, organization_id: UUID) -> Optional[BillingAccount]:
        """
        Retrieve the billing account for an organisation, or None if missing.

        Args:
            organization_id (UUID): The unique identifier of the organization to look up.

        Returns:
            Optional[BillingAccount]: The billing account for the organisation.
        """
        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        return await self.db.scalar(stmt)

    async def get_billing_account_by_id(self, account_id: UUID) -> BillingAccount | None:
        stmt = select(BillingAccount).where(BillingAccount.id == account_id)
        return await self.db.scalar(stmt)

    async def find_billing_account_by_customer_id(
        self, stripe_customer_id: str
    ) -> Optional[BillingAccount]:
        """
        Find a BillingAccount by its Stripe customer id.

        Args:
            stripe_customer_id: The stripe Customer ID (e.g. 'cus_...').

        Returns:
            BillingAccount or None if not found.
        """
        stmt = select(BillingAccount).where(BillingAccount.stripe_customer_id == stripe_customer_id)
        return await self.db.scalar(stmt)

    async def add_payment_method(
        self,
        billing_account_id: UUID,
        stripe_payment_method_id: str,
        card_brand: Optional[str] = None,
        last4: Optional[str] = None,
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        is_default: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentMethod:
        """
        Create a non-sensitive payment-method record for a billing account.

        Args:
            billing_account_id (UUID): ID of the billing account to attach the payment method to.
            stripe_payment_method_id (str): Stripe PaymentMethod identifier (non-sensitive).
            card_brand (Optional[str]): Card brand (e.g., "visa", "mastercard"), if known.
            last4 (Optional[str]): Last 4 digits of the card number, if known.
            exp_month (Optional[int]): Card expiration month (1-12), if known.
            exp_year (Optional[int]): Card expiration year (four digits), if known.
            is_default (bool): Whether this payment method should be the account's default.
            metadata (Optional[Dict[str, Any]]): metadata to attach to the payment method

        Returns:
            PaymentMethod: The newly created and persisted PaymentMethod

        Raises:
            ValueError: If the billing account with the provided ID does not exist.
            Exception: On database errors or other unexpected failures; the transaction
                will be rolled back before the exception is propagated.
        """
        acct_stmt = select(BillingAccount).where(BillingAccount.id == billing_account_id)
        account = await self.db.scalar(acct_stmt)
        if not account:
            raise ValueError("Billing account not found")

        pm = PaymentMethod(
            billing_account_id=billing_account_id,
            stripe_payment_method_id=stripe_payment_method_id,
            card_brand=card_brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
            metadata_=(metadata or {}),
        )

        try:
            if is_default:
                await self._clear_default_payment_method(billing_account_id)

            self.db.add(pm)
            await self.db.flush()
            await self.db.refresh(pm)

            if account.stripe_customer_id:
                await stripe_attach_payment_method(
                    customer_id=account.stripe_customer_id,
                    payment_method_id=stripe_payment_method_id,
                    set_as_default=is_default,
                )
                logger.info(
                    "Attached payment method %s to stripe customer %s",
                    stripe_payment_method_id,
                    account.stripe_customer_id,
                )

            await self.db.commit()
            await self.db.refresh(pm)

            if is_default is False and account.default_payment_method_id is None:
                await self.set_default_payment_method(
                    billing_account_id=billing_account_id, payment_method_id=pm.id
                )

            logger.info("Added payment method %s for billing_account=%s", pm.id, billing_account_id)
            return pm

        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to add payment method for billing_account=%s: %s", billing_account_id, exc
            )
            raise

    async def _clear_default_payment_method(self, billing_account_id: UUID) -> None:
        """Clear the is_default flag on all payment methods for an account."""
        try:
            stmt = (
                update(PaymentMethod)
                .where(
                    PaymentMethod.billing_account_id == billing_account_id,
                    PaymentMethod.is_default,
                )
                .values(is_default=False)
            )
            await self.db.execute(stmt)
        except Exception:
            logger.exception("Failed to clear default payment methods for %s", billing_account_id)
            raise

    async def set_default_payment_method(
        self, billing_account_id: UUID, payment_method_id: UUID
    ) -> PaymentMethod:
        """
        Set a payment method as the account default

        Args:
            billing_account_id (UUID): ID of the billing account to update.
            payment_method_id (UUID): ID of the payment method to set as default.

        Returns:
            PaymentMethod: The PaymentMethod instance that was set as the default.

        Raises:
            ValueError: If the payment method does not belong to the specified billing account
                or if the billing account is not found.
            Exception: On database or transaction errors;
                the transaction will be rolled back before the exception is re-raised.
        """
        try:
            pm_check = await self.db.scalar(
                select(PaymentMethod).where(PaymentMethod.id == payment_method_id)
            )
            if not pm_check or pm_check.billing_account_id != billing_account_id:
                raise ValueError("Payment method not found for billing account")

            stmt = (
                update(PaymentMethod)
                .where(PaymentMethod.billing_account_id == billing_account_id)
                .values(
                    is_default=case(
                        (PaymentMethod.id == payment_method_id, True),
                        else_=False,
                    )
                )
                .returning(PaymentMethod)
            )
            result = await self.db.execute(stmt)
            pm = None
            for row in result.scalars():
                if row.is_default:
                    pm = row
            if not pm:
                raise ValueError("Payment method not found while setting default")

            acct_stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == billing_account_id)
                .values(default_payment_method_id=payment_method_id)
                .returning(BillingAccount)
            )
            account_result = await self.db.execute(acct_stmt)
            account = account_result.scalar_one_or_none()
            if not account:
                raise ValueError("Billing account not found")

            await self.db.commit()
            await self.db.refresh(pm)

            if account.stripe_customer_id and pm.stripe_payment_method_id:
                try:
                    await stripe_attach_payment_method(
                        customer_id=account.stripe_customer_id,
                        payment_method_id=pm.stripe_payment_method_id,
                        set_as_default=True,
                    )
                    logger.info(
                        "Updated stripe default payment method customer=%s pm=%s",
                        account.stripe_customer_id,
                        pm.stripe_payment_method_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to update stripe default payment method for customer=%s",
                        account.stripe_customer_id,
                    )

            logger.info(
                "Set payment method %s as default for account %s",
                payment_method_id,
                billing_account_id,
            )
            return pm

        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to set default payment method %s for account %s",
                payment_method_id,
                billing_account_id,
            )
            raise

    async def find_payment_method_by_stripe_id(
        self, stripe_payment_method_id: str
    ) -> Optional[PaymentMethod]:
        """
        Find a local PaymentMethod by its Stripe payment_method id.
        """
        stmt = select(PaymentMethod).where(
            PaymentMethod.stripe_payment_method_id == stripe_payment_method_id
        )
        return await self.db.scalar(stmt)

    async def delete_payment_method(self, payment_method_id: UUID) -> bool:
        """
        Delete a payment method record. If it was default, clear on billing account.

        Args:
            payment_method_id (UUID): Identifier of the payment method to delete.

        Returns:
            bool: True if the payment method existed and was deleted; False if no such
            payment method was found.

        Raises:
            Exception: If an error occurs during database operations; the transaction is
            rolled back and the exception is re-raised.
        """
        try:
            stmt = select(PaymentMethod).where(PaymentMethod.id == payment_method_id)
            pm = await self.db.scalar(stmt)
            if not pm:
                return False

            billing_account_id = pm.billing_account_id
            stripe_pm_id = pm.stripe_payment_method_id
            was_default = pm.is_default

            await self.db.delete(pm)

            if was_default:
                await self.db.execute(
                    update(BillingAccount)
                    .where(BillingAccount.id == billing_account_id)
                    .values(default_payment_method_id=None)
                )

            await self.db.commit()
            logger.info(
                "Deleted payment method %s (was_default=%s)", payment_method_id, was_default
            )

            if stripe_pm_id:
                try:
                    await stripe_detach_payment_method(stripe_pm_id)
                    logger.info("Detached stripe payment method %s", stripe_pm_id)
                except Exception:
                    logger.exception("Failed to detach stripe payment method %s", stripe_pm_id)

            return True
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to delete payment method %s", payment_method_id)
            raise

    async def list_payment_methods(self, billing_account_id: UUID) -> List[PaymentMethod]:
        """
        Return all payment methods associated with the given billing account.

        Args:
            billing_account_id (UUID): UUID of the billing account.

        Returns:
            List[PaymentMethod]: A list of PaymentMethod objects for the specified billing account.
        """
        stmt = select(PaymentMethod).where(PaymentMethod.billing_account_id == billing_account_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def attach_stripe_customer(
        self,
        billing_account_id: UUID,
        stripe_customer_id: str,
        stripe_subscription_id: Optional[str] = None,
    ) -> BillingAccount:
        """
        Attach Stripe customer and (optionally) subscription id to an account.

        Args:
            billing_account_id (UUID): The ID of the billing account to update.
            stripe_customer_id (str): The Stripe customer ID to associate with the billing account.
            stripe_subscription_id (Optional[str]): Optional Stripe subscription ID.

        Returns:
            BillingAccount: The updated and refreshed BillingAccount object with the new Stripe IDs.

        Raises:
            ValueError: If no BillingAccount exists with the provided billing_account_id.
            Exception: For unexpected failures during the database update;
                the operation will be rolled back on error.
        """
        try:
            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == billing_account_id)
                .values(
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                )
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            await self.db.commit()
            if not account:
                raise ValueError("Billing account not found")
            await self.db.refresh(account)
            logger.info(
                "Attached stripe customer %s to billing_account=%s",
                stripe_customer_id,
                billing_account_id,
            )
            return account
        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to attach stripe customer to billing account %s", billing_account_id
            )
            raise

    @staticmethod
    def _map_stripe_invoice_status(stripe_status: Optional[str]) -> InvoiceStatus:
        """
        Map Stripe's invoice.status -> our InvoiceStatus enum.
        """
        if not stripe_status:
            return InvoiceStatus.PENDING

        mapping = {
            "draft": InvoiceStatus.DRAFT,
            "open": InvoiceStatus.OPEN,
            "paid": InvoiceStatus.PAID,
            "void": InvoiceStatus.VOID,
            "uncollectible": InvoiceStatus.FAILED,
        }
        return mapping.get(stripe_status, InvoiceStatus.PENDING)

    async def create_stripe_and_local_invoice(
        self,
        billing_account_id: UUID,
        stripe_price_id: str,
        quantity: int = 1,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InvoiceHistory:
        """
        Convenience helper: create a real Stripe invoice for this billing account,
        based on a Stripe Price + quantity, and persist a matching InvoiceHistory
        record that mirrors the Stripe invoice.

        Flow:
        - Load the BillingAccount and ensure it has a Stripe customer id.
        - Use Stripe to create an invoice item using `stripe_price_id` and `quantity`,
        then create + finalize a Stripe Invoice for that customer.
        - Map the Stripe invoice fields into our local InvoiceHistory table
        (amount_due, amount_paid, status, URLs, metadata, etc.).
        """
        acct_stmt = select(BillingAccount).where(BillingAccount.id == billing_account_id)
        account = await self.db.scalar(acct_stmt)
        if not account:
            raise ValueError("Billing account not found")

        if not account.stripe_customer_id:
            raise ValueError("Billing account has no Stripe customer id")

        stripe_invoice: Dict[str, Any] = await stripe_create_invoice_for_customer_with_price_id(
            customer_id=account.stripe_customer_id,
            price_id=stripe_price_id,
            quantity=quantity,
            description=description,
            metadata=metadata or {},
        )

        pi = stripe_invoice.get("payment_intent")
        stripe_payment_intent_id: Optional[str] = None
        if isinstance(pi, dict):
            stripe_payment_intent_id = pi.get("id")
        elif isinstance(pi, str):
            stripe_payment_intent_id = pi

        stripe_status = stripe_invoice.get("status")
        hosted_invoice_url = stripe_invoice.get("hosted_invoice_url")
        invoice_pdf_url = stripe_invoice.get("invoice_pdf")

        total = stripe_invoice.get("total") or stripe_invoice.get("amount_due") or 0
        amount_paid = stripe_invoice.get("amount_paid") or 0

        status = self._map_stripe_invoice_status(stripe_status)

        return await self.create_invoice_record(
            billing_account_id=billing_account_id,
            amount_due=total,
            amount_paid=amount_paid,
            currency=stripe_invoice["currency"],
            stripe_invoice_id=stripe_invoice["id"],
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=status,
            metadata=stripe_invoice.get("metadata"),
            hosted_invoice_url=hosted_invoice_url,
            invoice_pdf_url=invoice_pdf_url,
        )

    async def create_invoice_record(
        self,
        billing_account_id: UUID,
        amount_due: int,
        amount_paid: int = 0,
        currency: str = DEFAULT_CURRENCY,
        stripe_invoice_id: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
        status: InvoiceStatus = InvoiceStatus.DRAFT,
        metadata: Optional[Dict[str, Any]] = None,
        hosted_invoice_url: Optional[str] = None,
        invoice_pdf_url: Optional[str] = None,
    ) -> InvoiceHistory:
        """
        Create an invoice record for a billing account.

        Args:
            billing_account_id (UUID): ID of the billing account to associate the invoice with.
            amount_due (int): Amount due in cents.
            currency (str, optional): ISO currency code. Defaults to DEFAULT_CURRENCY.
            stripe_invoice_id (Optional[str], optional): Optional Stripe invoice ID.
            stripe_payment_intent_id (Optional[str], optional): Optional Stripe payment intent ID.
            status (InvoiceStatus, optional): Initial invoice status. Defaults - InvoiceStatus.DRAFT
            metadata (Optional[Dict[str, Any]], optional): metadata to attach to the invoice.

        Returns:
            InvoiceHistory: The newly created and persisted InvoiceHistory instance.

        Raises:
            Exception: Any exception raised during database operations is propagated.
        """
        invoice = InvoiceHistory(
            billing_account_id=billing_account_id,
            stripe_invoice_id=stripe_invoice_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            amount_due=amount_due,
            amount_paid=amount_paid,
            currency=currency.upper(),
            status=status,
            hosted_invoice_url=hosted_invoice_url,
            invoice_pdf_url=invoice_pdf_url,
            metadata_=(metadata or {}),
        )

        try:
            self.db.add(invoice)
            await self.db.flush()
            await self.db.refresh(invoice)
            await self.db.commit()
            logger.info("Created invoice %s for billing_account=%s", invoice.id, billing_account_id)
            return invoice
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to create invoice for billing_account=%s", billing_account_id)
            raise

    async def mark_invoice_paid(
        self, invoice_id: UUID, amount_paid: Optional[int] = None
    ) -> InvoiceHistory:
        """
        Mark an invoice as paid and persist the updated invoice to the database.

        Args:
            invoice_id (UUID): The unique identifier of the invoice to mark as paid.
            amount_paid (Optional[int], optional): The amount that was paid. If None,
                the invoice's amount_due will be used (treating it as full payment).

        Returns:
            InvoiceHistory: The updated InvoiceHistory instance reflecting the new
            amount_paid and status.

        Raises:
            ValueError: If no invoice with the given invoice_id exists.
            Exception: Propagates any database or unexpected errors after rolling back
                the transaction.
        """
        try:
            stmt = select(InvoiceHistory).where(InvoiceHistory.id == invoice_id)
            invoice = await self.db.scalar(stmt)
            if not invoice:
                raise ValueError("Invoice not found")

            if amount_paid is not None:
                invoice.amount_paid = amount_paid
            else:
                invoice.amount_paid = invoice.amount_due

            invoice.status = InvoiceStatus.PAID
            self.db.add(invoice)
            await self.db.flush()
            await self.db.refresh(invoice)
            await self.db.commit()

            logger.info("Marked invoice %s as PAID", invoice_id)
            return invoice
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to mark invoice %s as paid", invoice_id)
            raise

    async def mark_invoice_failed(self, invoice_id: UUID) -> InvoiceHistory:
        """
        Mark an invoice as failed/failed payment attempt.

        Args:
            invoice_id (UUID): Unique identifier of the invoice to mark as failed.
        Returns:
            InvoiceHistory: The updated InvoiceHistory instance with status set to FAILED.
        Raises:
            ValueError: If no invoice exists with the given invoice_id.
            Exception: Any unexpected exception encountered is re-raised after rollback.
        """
        try:
            stmt = select(InvoiceHistory).where(InvoiceHistory.id == invoice_id)
            invoice = await self.db.scalar(stmt)
            if not invoice:
                raise ValueError("Invoice not found")

            invoice.status = InvoiceStatus.FAILED
            self.db.add(invoice)
            await self.db.flush()
            await self.db.refresh(invoice)
            await self.db.commit()

            logger.info("Marked invoice %s as FAILED", invoice_id)
            return invoice
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to mark invoice %s as failed", invoice_id)
            raise

    async def get_invoices_for_account(self, billing_account_id: UUID) -> List[InvoiceHistory]:
        """
        Return invoices for a billing account ordered by creation time (newest first).

        Args:
            billing_account_id (UUID): The UUID of the billing account to fetch invoices for.

        Returns:
            List[InvoiceHistory]: A list of InvoiceHistory objects belonging to the specified
                billing account, ordered by `created_at` in descending order. Returns an empty
                list if no invoices are found.
        """
        stmt = (
            select(InvoiceHistory)
            .where(InvoiceHistory.billing_account_id == billing_account_id)
            .order_by(InvoiceHistory.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def find_invoice_by_stripe_invoice_id(
        self, stripe_invoice_id: str
    ) -> Optional[InvoiceHistory]:
        """
        Find a local InvoiceHistory record by Stripe invoice id.

        Args:
            stripe_invoice_id: The stripe invoice id (e.g. 'in_...').

        Returns:
            InvoiceHistory or None if not found.
        """
        stmt = select(InvoiceHistory).where(InvoiceHistory.stripe_invoice_id == stripe_invoice_id)
        return await self.db.scalar(stmt)

    async def find_invoice_by_payment_intent_id(
        self, stripe_payment_intent_id: str
    ) -> Optional[InvoiceHistory]:
        """
        Find a local InvoiceHistory record by Stripe PaymentIntent id.

        Args:
            stripe_payment_intent_id: The stripe PaymentIntent id (e.g. 'pi_...').

        Returns:
            InvoiceHistory or None if not found.
        """
        stmt = select(InvoiceHistory).where(
            InvoiceHistory.stripe_payment_intent_id == stripe_payment_intent_id
        )
        return await self.db.scalar(stmt)

    async def get_subscription_overview_for_org(
        self, organization_id: UUID
    ) -> Optional[BillingAccount]:
        """
        Convenience helper: return the BillingAccount for an org so the API
        can expose subscription-related fields.
        """
        return await self.get_billing_account_by_org(organization_id)

    async def cancel_subscription_for_account(
        self,
        account: BillingAccount,
        cancel_at_period_end: bool = True,
    ) -> BillingAccount:
        """
        Cancel the Stripe subscription for this account.

        - If cancel_at_period_end=True → subscription remains ACTIVE/ TRIALING
          until end of period, and we set cancel_at_period_end flag.
        - If False → cancel immediately and mark status CANCELLED.
        """
        if not account.stripe_subscription_id:
            raise ValueError("Billing account has no Stripe subscription id")

        try:
            stripe_sub = await stripe_cancel_subscription(
                subscription_id=account.stripe_subscription_id,
                cancel_at_period_end=cancel_at_period_end,
            )

            update_values: Dict[str, Any] = {
                "cancel_at_period_end": cancel_at_period_end,
            }

            if not cancel_at_period_end:
                update_values["status"] = BillingStatus.CANCELLED

            period = stripe_sub.get("current_period_end")
            if period:
                try:
                    update_values["current_period_end"] = datetime.fromtimestamp(
                        int(period), tz=timezone.utc
                    )
                except Exception:
                    logger.warning("Failed to parse current_period_end=%s from stripe", period)

            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == account.id)
                .values(**update_values)
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            updated = result.scalar_one_or_none()
            await self.db.commit()

            if not updated:
                raise ValueError("Billing account not found during cancel update")

            await self.db.refresh(updated)

            logger.info(
                "Cancelled subscription for account=%s (cancel_at_period_end=%s)",
                account.id,
                cancel_at_period_end,
            )
            return updated

        except Exception:
            await self.db.rollback()
            logger.exception("Failed to cancel subscription for billing_account=%s", account.id)
            raise

    async def update_subscription_price_for_account(
        self,
        account: BillingAccount,
        new_price_id: str,
    ) -> BillingAccount:
        """
        Change the Stripe subscription price for an account and persist the new price id.
        """
        if not account.stripe_subscription_id:
            raise ValueError("Billing account has no Stripe subscription id")

        account_id = account.id
        subscription_id = account.stripe_subscription_id
        account_status = getattr(account, "status", None)

        if account_status == "canceled":
            raise ValueError("Subscription is canceled and cannot be changed.")

        try:
            await stripe_update_subscription_price(
                subscription_id=subscription_id,
                new_price_id=new_price_id,
            )

            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == account_id)
                .values(current_price_id=new_price_id)
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            updated = result.scalar_one_or_none()

            if not updated:
                await self.db.rollback()
                raise ValueError("Billing account not found during plan change")

            await self.db.commit()
            await self.db.refresh(updated)

            logger.info(
                "Updated subscription price for billing_account=%s to price=%s",
                new_price_id,
            )
            return updated

        except SubscriptionAlreadyCanceledError as e:
            await self.db.rollback()
            logger.warning(
                "Attempted to change plan on canceled subscription: billing_account=%s",
                account_id,
            )
            raise ValueError(str(e)) from e

        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to update subscription price for billing_account=%s",
                account_id,
            )
            raise

    async def sync_subscription_from_stripe(
        self,
        account: BillingAccount,
    ) -> BillingAccount:
        """
        (Optional helper) Use Stripe as source-of-truth for subscription status
        and update local BillingAccount.

        You can call this from a 'refresh' endpoint if needed.
        """
        if not account.stripe_subscription_id:
            raise ValueError("Billing account has no Stripe subscription id")

        try:
            sub = await stripe_retrieve_subscription(account.stripe_subscription_id)

            stripe_status = sub.get("status")
            period_start = sub.get("current_period_start")
            period_end = sub.get("current_period_end")
            cancel_at_period_end = sub.get("cancel_at_period_end", False)

            mapped_status = account.status
            if stripe_status in ("active", "trialing"):
                mapped_status = BillingStatus.ACTIVE
            elif stripe_status == "past_due":
                mapped_status = BillingStatus.PAST_DUE
            elif stripe_status in ("incomplete", "incomplete_expired", "unpaid"):
                mapped_status = BillingStatus.UNPAID
            elif stripe_status in ("canceled", "cancelled"):
                mapped_status = BillingStatus.CANCELLED

            update_values: Dict[str, Any] = {
                "status": mapped_status,
                "cancel_at_period_end": cancel_at_period_end,
            }

            if period_start:
                try:
                    update_values["current_period_start"] = datetime.fromtimestamp(
                        int(period_start), tz=timezone.utc
                    )
                except Exception:
                    logger.warning("Failed to parse current_period_start=%s", period_start)

            if period_end:
                try:
                    update_values["current_period_end"] = datetime.fromtimestamp(
                        int(period_end), tz=timezone.utc
                    )
                except Exception:
                    logger.warning("Failed to parse current_period_end=%s", period_end)

            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == account.id)
                .values(**update_values)
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            updated = result.scalar_one_or_none()
            await self.db.commit()

            if not updated:
                raise ValueError("Billing account not found during sync")

            await self.db.refresh(updated)
            logger.info(
                "Synced subscription from Stripe for billing_account=%s (status=%s)",
                account.id,
                updated.status.value,
            )
            return updated
        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to sync subscription from Stripe for billing_account=%s", account.id
            )
            raise


def get_billing_service(db: AsyncSession) -> BillingService:
    """
    Convenience factory used by route dependencies to obtain a BillingService instance.

    Args:
        db (AsyncSession): Asynchronous database session used to initialize the service.

    Returns:
        BillingService: An instance of BillingService bound to the provided database session.
    """
    return BillingService(db)
