import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.redis_service import get_redis_client
from app.api.modules.v1.billing.models import BillingStatus, InvoiceHistory
from app.api.modules.v1.billing.service.billing_service import get_billing_service

logger = logging.getLogger(__name__)


_EVENT_KEY_PREFIX = "stripe_event_processed:"
_EVENT_TTL_SECONDS = 30 * 24 * 3600


async def _mark_event_processed(event_id: str) -> None:
    """
    Record that an event has been processed by setting a Redis key (SET with NX).
    """
    client = await get_redis_client()
    key = _EVENT_KEY_PREFIX + event_id
    try:
        try:
            await client.set(key, "1", ex=_EVENT_TTL_SECONDS, nx=True)
        except TypeError:
            was_set = await client.setnx(key, "1")
            if was_set:
                await client.expire(key, _EVENT_TTL_SECONDS)
        logger.debug("Marked stripe event processed: %s", event_id)
    except Exception:
        logger.exception("Failed to mark stripe event processed: %s", event_id)


async def _is_event_processed(event_id: str) -> bool:
    """
    Check if an event id has already been processed.
    """
    client = await get_redis_client()
    key = _EVENT_KEY_PREFIX + event_id
    try:
        exists = await client.exists(key)
        return bool(exists)
    except Exception:
        logger.exception("Failed to check processed state for stripe event: %s", event_id)
        return False


async def _handle_invoice_event(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle invoice related events using BillingService helper lookups.
    """
    billing_service = get_billing_service(db)
    stripe_invoice_id = data.get("id")
    status = data.get("status")
    amount_paid = data.get("amount_paid") or 0

    if not stripe_invoice_id:
        logger.warning("Invoice event with no id: %s", data)
        return {"action": "invoice_invalid_payload", "details": {}}

    try:
        invoice = await billing_service.find_invoice_by_stripe_invoice_id(stripe_invoice_id)
        if invoice:
            if status in ("paid", "paidout", "open"):
                await billing_service.mark_invoice_paid(
                    invoice_id=invoice.id, amount_paid=amount_paid
                )
                return {"action": "invoice_marked_paid", "invoice_id": str(invoice.id)}
            elif status in ("void", "uncollectible", "draft", "failed"):
                await billing_service.mark_invoice_failed(invoice_id=invoice.id)
                return {"action": "invoice_marked_failed", "invoice_id": str(invoice.id)}
            else:
                logger.info("Unhandled invoice status=%s for invoice=%s", status, stripe_invoice_id)
                return {"action": "invoice_status_unhandled", "status": status}
        else:
            logger.info("No local invoice found for stripe_invoice_id=%s", stripe_invoice_id)
            return {"action": "invoice_not_found", "stripe_invoice_id": stripe_invoice_id}
    except Exception:
        logger.exception("Error handling invoice event for stripe_invoice_id=%s", stripe_invoice_id)
        raise


async def _handle_payment_intent_event(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle payment_intent events (succeeded / payment_failed).
    Attempts to find local invoice by stripe_payment_intent_id and mark paid/failed.
    """
    billing_service = get_billing_service(db)
    pi_id = data.get("id")
    amount = data.get("amount_received") or data.get("amount") or 0
    status = data.get("status")

    if not pi_id:
        logger.warning("PaymentIntent event with no id: %s", data)
        return {"action": "payment_intent_invalid_payload", "details": {}}

    try:
        invoice: InvoiceHistory | None = await billing_service.find_invoice_by_payment_intent_id(
            stripe_payment_intent_id=pi_id
        )

        if not invoice:
            logger.info("No local invoice found for payment_intent=%s", pi_id)
            return {"action": "payment_intent_invoice_not_found", "payment_intent": pi_id}

        if status == "succeeded":
            updated = await billing_service.mark_invoice_paid(
                invoice_id=invoice.id,
                amount_paid=amount,
            )
            return {"action": "payment_succeeded", "invoice_id": str(updated.id)}
        else:
            updated = await billing_service.mark_invoice_failed(invoice_id=invoice.id)
            return {"action": "payment_failed", "invoice_id": str(updated.id)}

    except Exception:
        logger.exception("Error handling payment_intent event for pi=%s", pi_id)
        raise


async def _handle_subscription_event(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle subscription events to update BillingAccount periods and status.
    Uses BillingService.attach_stripe_customer to atomically attach subscription id,
    then updates period/price/status via the service or a safe update.
    """
    billing_service = get_billing_service(db)
    customer_id = data.get("customer")
    sub_id = data.get("id")
    current_period_start = data.get("current_period_start")
    current_period_end = data.get("current_period_end")
    status = data.get("status")
    price_id = None

    items = (
        data.get("items", {}).get("data")
        if isinstance(data.get("items"), dict)
        else data.get("items")
    )
    if items and isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict):
        price_id = items[0].get("price", {}).get("id") or items[0].get("price")

    if not customer_id:
        logger.warning("Subscription event missing customer: %s", data)
        return {"action": "subscription_invalid_payload", "details": {}}

    try:
        account = await billing_service.find_billing_account_by_customer_id(customer_id)
        if not account:
            logger.info("No billing account matched stripe customer %s", customer_id)
            return {"action": "billing_account_not_found", "stripe_customer_id": customer_id}

        await billing_service.attach_stripe_customer(
            billing_account_id=account.id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=sub_id,
        )

        mapped_status = None
        if status in ("active", "trialing"):
            mapped_status = BillingStatus.ACTIVE
        elif status in ("past_due",):
            mapped_status = BillingStatus.PAST_DUE
        elif status in ("incomplete", "incomplete_expired", "unpaid"):
            mapped_status = BillingStatus.UNPAID
        elif status in ("canceled", "cancelled"):
            mapped_status = BillingStatus.CANCELLED

        update_values: Dict[str, Any] = {}
        if current_period_start:
            try:
                update_values["current_period_start"] = datetime.fromtimestamp(
                    int(current_period_start), tz=timezone.utc
                )
            except Exception:
                logger.warning("Failed to parse current_period_start=%s", current_period_start)
        if current_period_end:
            try:
                update_values["current_period_end"] = datetime.fromtimestamp(
                    int(current_period_end), tz=timezone.utc
                )
            except Exception:
                logger.warning("Failed to parse current_period_end=%s", current_period_end)
        if price_id:
            update_values["current_price_id"] = price_id
        if mapped_status:
            update_values["status"] = mapped_status

        if update_values:
            from sqlalchemy import update

            from app.api.modules.v1.billing.models.billing_account import BillingAccount as BA

            if "status" in update_values and hasattr(update_values["status"], "value"):
                update_values["status"] = update_values["status"].value
            stmt = (
                update(BA)
                .where(BA.id == account.id)
                .values(**update_values)
                .execution_options(synchronize_session="fetch")
            )
            await db.execute(stmt)
            await db.commit()

        logger.info(
            "Processed subscription event for subscription=%s customer=%s", sub_id, customer_id
        )
        return {"action": "subscription_processed", "billing_account_id": str(account.id)}
    except Exception:
        await db.rollback()
        logger.exception("Error handling subscription event for subscription=%s", sub_id)
        raise


async def _handle_checkout_session_completed(
    db: AsyncSession, data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle `checkout.session.completed`.

    We mainly:
    - Resolve the BillingAccount via metadata or customer id.
    - Optionally attach subscription id if present.
    - Log and return a structured action.

    Most of the real billing-state changes are still handled by
    customer.subscription.* events, which is the recommended pattern.
    """
    billing_service = get_billing_service(db)

    session_id = data.get("id")
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    metadata = data.get("metadata") or {}

    org_id = metadata.get("organization_id")
    billing_account_id = metadata.get("billing_account_id")
    plan = metadata.get("plan")

    account = None
    if billing_account_id:
        account = await billing_service.get_billing_account_by_id(billing_account_id)

    if not account and customer_id:
        account = await billing_service.find_billing_account_by_customer_id(customer_id)

    if not account:
        logger.info(
            "Checkout session completed but no billing account found "
            "session=%s customer=%s metadata=%s",
            session_id,
            customer_id,
            metadata,
        )
        return {
            "action": "checkout_completed_account_not_found",
            "session_id": session_id,
            "customer_id": customer_id,
            "organization_id": org_id,
        }

    if subscription_id and not account.stripe_subscription_id:
        await billing_service.attach_stripe_customer(
            billing_account_id=account.id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
        )

    logger.info(
        "Checkout session completed for billing_account=%s plan=%s session=%s subscription=%s",
        account.id,
        plan,
        session_id,
        subscription_id,
    )

    return {
        "action": "checkout_session_completed",
        "billing_account_id": str(account.id),
        "organization_id": org_id,
        "plan": plan,
        "session_id": session_id,
        "subscription_id": subscription_id,
    }


async def _handle_payment_method_attached(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle `payment_method.attached`.

    Goal:
    - Resolve BillingAccount via stripe_customer_id.
    - If we don't already have a PaymentMethod for this stripe pm, create one
      using BillingService.add_payment_method.
    """
    billing_service = get_billing_service(db)

    pm_id = data.get("id")
    customer_id = data.get("customer")
    if not pm_id or not customer_id:
        logger.warning("payment_method.attached missing id/customer: %s", data)
        return {"action": "payment_method_invalid_payload", "details": {}}

    existing = await billing_service.find_payment_method_by_stripe_id(pm_id)
    if existing:
        logger.info(
            "payment_method.attached for already-recorded pm=%s (id=%s)",
            pm_id,
            existing.id,
        )
        return {
            "action": "payment_method_already_recorded",
            "payment_method_id": str(existing.id),
            "stripe_payment_method_id": pm_id,
        }

    account = await billing_service.find_billing_account_by_customer_id(customer_id)
    if not account:
        logger.info(
            "payment_method.attached but no billing account found for customer=%s",
            customer_id,
        )
        return {
            "action": "payment_method_account_not_found",
            "customer_id": customer_id,
        }

    card = data.get("card") or {}
    brand = card.get("brand")
    last4 = card.get("last4")
    exp_month = card.get("exp_month")
    exp_year = card.get("exp_year")

    pm = await billing_service.add_payment_method(
        billing_account_id=account.id,
        stripe_payment_method_id=pm_id,
        card_brand=brand,
        last4=last4,
        exp_month=exp_month,
        exp_year=exp_year,
        is_default=True,
        metadata={"source": "webhook_payment_method.attached"},
    )

    logger.info(
        "Created local payment method %s from webhook for billing_account=%s",
        pm.id,
        account.id,
    )

    return {
        "action": "payment_method_attached_recorded",
        "payment_method_id": str(pm.id),
        "billing_account_id": str(account.id),
        "stripe_payment_method_id": pm_id,
        "customer_id": customer_id,
    }


async def process_stripe_event(db: AsyncSession, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Top-level dispatcher to process a stripe.Event object.
    """
    event_id = event.get("id")
    event_type = event.get("type")
    if not event_id or not event_type:
        logger.warning("Invalid stripe event payload (missing id/type)")
        return {"processed": False, "action": "invalid_event", "details": {}}

    try:
        if await _is_event_processed(event_id):
            logger.info("Stripe event already processed: %s", event_id)
            return {"processed": False, "action": "already_processed", "event_id": event_id}
    except Exception:
        logger.warning("Idempotency check failed for event %s; proceeding", event_id)

    data_obj = event.get("data", {}).get("object", {}) or {}
    result = {"processed": True, "action": "unhandled_event", "event_type": event_type}

    try:
        if event_type.startswith("invoice."):
            result = await _handle_invoice_event(db, data_obj)

        elif event_type.startswith("payment_intent."):
            result = await _handle_payment_intent_event(db, data_obj)

        elif event_type.startswith("customer.subscription.") or event_type.startswith(
            "subscription."
        ):
            result = await _handle_subscription_event(db, data_obj)

        elif event_type == "checkout.session.completed":
            result = await _handle_checkout_session_completed(db, data_obj)

        elif event_type == "payment_method.attached":
            result = await _handle_payment_method_attached(db, data_obj)

        # common event are no-opped but I logged here
        elif event_type == "charge.succeeded":
            charge_id = data_obj.get("id")
            pi_id = data_obj.get("payment_intent")
            logger.info(
                "Charge succeeded (no-op, handled via payment_intent): charge=%s payment_intent=%s",
                charge_id,
                pi_id,
            )
            result = {
                "action": "charge_succeeded_noop",
                "charge_id": charge_id,
                "payment_intent_id": pi_id,
            }

        elif event_type == "invoice_payment.paid":
            logger.info(
                "Invoice payment paid (no-op, invoice payments not modelled locally): %s",
                data_obj.get("id"),
            )
            result = {
                "action": "invoice_payment_paid_noop",
                "invoice_payment_id": data_obj.get("id"),
            }

        else:
            logger.info("Unhandled stripe event type: %s", event_type)
            result = {"action": "unhandled_event_type", "event_type": event_type}

        try:
            await _mark_event_processed(event_id)
        except Exception:
            pass

        return {"processed": True, "action": result.get("action"), "details": result}
    except Exception as exc:
        logger.exception("Failed to process stripe event %s: %s", event_id, str(exc))
        return {"processed": False, "action": "processing_failed", "error": str(exc)}
