import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.logger import setup_logging
from app.api.db.database import get_db
from app.api.modules.v1.billing.models import (
    BillingAccount,
    InvoiceHistory,
    StripeEventLog,
    Subscription,
)

setup_logging()
logger = logging.getLogger(__name__) 

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Stripe webhook endpoint (async)"""
    logger.info("Received Stripe webhook")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        logger.error("Missing Stripe signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )
    
    # Check idempotency
    event_statement = select(StripeEventLog).where(
        StripeEventLog.event_id == event.id
    )
    result = await db.execute(event_statement)
    existing_event = result.scalar_one_or_none()
    
    if existing_event and existing_event.processed_success:
        logger.info("Event already processed", extra={
            "event_id": event.id,
            "event_type": event.type
        })
        return {"status": "already_processed"}
    
    # Log event
    event_log = StripeEventLog(
        event_id=event.id,
        type=event.type,
        object_type=event.data.object.object if hasattr(event.data.object, 'object') else None,
        payload=event.to_dict(),
        processed_at=datetime.utcnow(),
        processed_success=False
    )
    db.add(event_log)
    await db.commit()
    
    logger.info("Processing Stripe event", extra={
        "event_id": event.id,
        "event_type": event.type
    })
    
    # Handle specific events
    try:
        if event.type == "checkout.session.completed":
            await handle_checkout_completed(event, db)
        
        elif event.type == "invoice.payment_succeeded":
            await handle_invoice_payment_succeeded(event, db)
        
        # Mark as processed
        event_log.processed_success = True
        await db.commit()
        
        logger.info("Event processed successfully", extra={
            "event_id": event.id,
            "event_type": event.type
        })
        
        return {"status": "success"}
    
    except Exception as e:
        logger.error("Failed to process webhook event", exc_info=True, extra={
            "event_id": event.id,
            "event_type": event.type,
            "error": str(e)
        })
        
        event_log.processed_success = False
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process event"
        )

async def handle_checkout_completed(event: stripe.Event, db: AsyncSession):
    """Handle checkout.session.completed (async)"""
    session = event.data.object
    
    logger.info("Handling checkout.session.completed", extra={
        "session_id": session.id,
        "customer": session.customer
    })
    
    billing_account_id = session.metadata.get("billing_account_id")
    
    if not billing_account_id:
        logger.warning("No billing_account_id in metadata")
        return
    
    # Get billing account
    result = await db.get(BillingAccount, billing_account_id)
    billing_account = result
    
    if not billing_account:
        logger.error("Billing account not found", extra={
            "billing_account_id": billing_account_id
        })
        return
    
    subscription_id = session.subscription
    
    if subscription_id:
        import asyncio
        stripe_subscription = await asyncio.to_thread(
            stripe.Subscription.retrieve,
            subscription_id
        )
        
        subscription = Subscription(
            billing_account_id=billing_account.id,
            stripe_subscription_id=stripe_subscription.id,
            plan=session.metadata.get("plan", "monthly"),
            status=stripe_subscription.status,
            current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
            cancel_at_period_end=stripe_subscription.cancel_at_period_end,
            canceled_at=None,
            ended_at=None,
            is_active=True
        )
        
        db.add(subscription)
        await db.flush()
        
        # Consume trial immediately
        billing_account.trial_ends_at = datetime.utcnow()
        billing_account.status = "active"
        billing_account.current_subscription_id = subscription.id
        
        await db.commit()
        
        logger.info("Trial consumed immediately after successful payment", extra={
            "billing_account_id": str(billing_account.id),
            "subscription_id": str(subscription.id)
        })

async def handle_invoice_payment_succeeded(event: stripe.Event, db: AsyncSession):
    """Handle invoice.payment_succeeded (async)"""
    invoice = event.data.object
    
    logger.info("Handling invoice.payment_succeeded", extra={
        "invoice_id": invoice.id,
        "customer": invoice.customer
    })
    
    # Find billing account
    statement = select(BillingAccount).where(
        BillingAccount.stripe_customer_id == invoice.customer
    )
    result = await db.execute(statement)
    billing_account = result.scalar_one_or_none()
    
    if not billing_account:
        logger.warning("Billing account not found for customer", extra={
            "customer_id": invoice.customer
        })
        return
    
    # Check if invoice already exists
    invoice_statement = select(InvoiceHistory).where(
        InvoiceHistory.stripe_invoice_id == invoice.id
    )
    invoice_result = await db.execute(invoice_statement)
    existing_invoice = invoice_result.scalar_one_or_none()
    
    if existing_invoice:
        logger.info("Invoice already recorded")
        return
    
    # Create invoice record
    from decimal import Decimal
    invoice_record = InvoiceHistory(
        billing_account_id=billing_account.id,
        invoice_id=None,
        stripe_invoice_id=invoice.id,
        amount=Decimal(invoice.amount_paid) / 100,
        currency=invoice.currency,
        status=invoice.status,
        paid=invoice.paid,
        invoice_pdf_url=invoice.invoice_pdf,
        hosted_invoice_url=invoice.hosted_invoice_url,
        invoice_date=datetime.fromtimestamp(invoice.created),
        reason=None
    )
    
    db.add(invoice_record)
    
    # Consume trial if first payment
    if billing_account.status == "trialing":
        billing_account.trial_ends_at = datetime.utcnow()
        billing_account.status = "active"
        
        logger.info("Trial consumed on invoice payment", extra={
            "billing_account_id": str(billing_account.id),
            "invoice_id": invoice.id
        })
    
    # Reactivate if past_due/blocked
    elif billing_account.status in ["past_due", "blocked"]:
        billing_account.status = "active"
        billing_account.blocked_at = None
        
        logger.info("Billing account reactivated", extra={
            "billing_account_id": str(billing_account.id)
        })
    
    await db.commit()
