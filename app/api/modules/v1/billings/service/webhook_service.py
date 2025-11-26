import logging
from app.api.modules.v1.billings.schemas.webhook_schema import StripeEvent

logger = logging.getLogger("app")

async def handle_stripe_event(event: StripeEvent):
    """Process Stripe webhook events."""
    logger.info(f"Handling Stripe event: {event.type}")

    if event.type == "payment_intent.succeeded":
        logger.info(f"Payment succeeded: {event.data}")
        # Add your business logic here

    elif event.type == "invoice.payment_failed":
        logger.warning(f"Payment failed: {event.data}")
        # Add your business logic here

    else:
        logger.info(f"Unhandled event type: {event.type}")