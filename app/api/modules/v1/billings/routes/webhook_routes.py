from fastapi import APIRouter, HTTPException, Request, Header
from stripe import error as stripe_error
# Replace the existing import
# from stripe.error import SignatureVerificationError
# with the following:
SignatureVerificationError = stripe_error.SignatureVerificationError
from app.api.modules.v1.billings.service.webhook_service import handle_stripe_event
import stripe
import logging

logger = logging.getLogger("app")

router = APIRouter(prefix="/webhook", tags=["Billing Webhooks"])

# Replace with your Stripe secret key
stripe.api_key = "your-stripe-secret-key"

# Replace with your Stripe webhook secret
STRIPE_WEBHOOK_SECRET = "your-webhook-secret"

@router.post("/stripe")
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(...)
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    try:
        # Verify the webhook signature
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    try:
        await handle_stripe_event(event)
    except Exception as e:
        logger.exception(f"Error handling event: {e}")
        raise HTTPException(status_code=500, detail="Error handling event")

    return {"status": "success"}