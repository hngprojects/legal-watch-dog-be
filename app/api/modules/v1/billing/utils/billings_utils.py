import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.api.core.config import settings
from app.api.modules.v1.billing.models.billing_account import BillingStatus
from app.api.modules.v1.billing.models.invoice_history import InvoiceStatus

logger = logging.getLogger(__name__)

TRIAL_DURATION_DAYS = settings.TRIAL_DURATION_DAYS
DEFAULT_CURRENCY = "USD"


def parse_ts(value: Any, field_name: str) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except Exception:
        logger.warning("Failed to parse %s=%s", field_name, value)
        return None


def map_stripe_status_to_billing_status(stripe_status: str) -> BillingStatus:
    if stripe_status == "trialing":
        return BillingStatus.TRIALING
    if stripe_status == "active":
        return BillingStatus.ACTIVE
    if stripe_status == "past_due":
        return BillingStatus.PAST_DUE
    if stripe_status in ("incomplete", "incomplete_expired", "unpaid"):
        return BillingStatus.UNPAID
    if stripe_status in ("canceled", "cancelled"):
        return BillingStatus.CANCELLED
    return BillingStatus.UNPAID


def map_stripe_invoice_status(stripe_status: Optional[str]) -> InvoiceStatus:
    """
    Map Stripe's invoice.status -> our InvoiceStatus enum.
    Args:
        stripe_status (Optional[str]): The raw status value returned by Stripe.

    Returns:
        InvoiceStatus: The mapped internal invoice status, defaulting to PENDING.
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
