import asyncio
import logging
from typing import Any, Dict, List, Optional

import stripe

from app.api.core.config import settings
from app.api.core.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__) 

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeClient:
    """
    Async wrapper around Stripe API operations.
    """

    def __init__(self):
        self.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_key = self.api_key

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> stripe.Customer:
        """Create a new Stripe customer (async)"""
        logger.info("Creating Stripe customer", extra={
            "email": email,
            "name": name,
            "metadata": metadata
        })
        
        try:
            customer = await asyncio.to_thread(
                stripe.Customer.create,
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            logger.info("Stripe customer created successfully", extra={
                "stripe_customer_id": customer.id,
                "email": email
            })
            
            return customer
            
        except stripe.error.StripeError as e:
            logger.error("Failed to create Stripe customer", exc_info=True, extra={
                "email": email,
                "error": str(e)
            })
            raise

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        trial_period_days: Optional[int] = None
    ) -> stripe.checkout.Session:
        """Create a Stripe Checkout session (async)"""
        logger.info("Creating Stripe Checkout session", extra={
            "customer_id": customer_id,
            "price_id": price_id,
            "trial_period_days": trial_period_days,
            "metadata": metadata
        })
        
        try:
            session_params = {
                "customer": customer_id,
                "mode": "subscription",
                "line_items": [{
                    "price": price_id,
                    "quantity": 1
                }],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
                "payment_method_types": ["card"],
                "billing_address_collection": "required"
            }
            
            if trial_period_days and trial_period_days > 0:
                session_params["subscription_data"] = {
                    "trial_period_days": trial_period_days,
                    "metadata": metadata or {}
                }
            
            session = await asyncio.to_thread(
                stripe.checkout.Session.create,
                **session_params
            )
            
            logger.info("Checkout session created successfully", extra={
                "session_id": session.id,
                "customer_id": customer_id
            })
            
            return session
            
        except stripe.error.StripeError as e:
            logger.error("Failed to create checkout session", exc_info=True, extra={
                "customer_id": customer_id,
                "error": str(e)
            })
            raise

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> stripe.billing_portal.Session:
        """Create a Stripe Customer Portal session (async)"""
        logger.info("Creating Stripe portal session", extra={
            "customer_id": customer_id,
            "return_url": return_url
        })
        
        try:
            session = await asyncio.to_thread(
                stripe.billing_portal.Session.create,
                customer=customer_id,
                return_url=return_url
            )
            
            logger.info("Portal session created successfully", extra={
                "session_id": session.id,
                "customer_id": customer_id
            })
            
            return session
            
        except stripe.error.StripeError as e:
            logger.error("Failed to create portal session", exc_info=True, extra={
                "customer_id": customer_id,
                "error": str(e)
            })
            raise

    async def attach_payment_method(
        self,
        payment_method_id: str,
        customer_id: str
    ) -> stripe.PaymentMethod:
        """Attach a payment method to a customer (async)"""
        logger.info("Attaching payment method", extra={
            "payment_method_id": payment_method_id,
            "customer_id": customer_id
        })
        
        try:
            payment_method = await asyncio.to_thread(
                stripe.PaymentMethod.attach,
                payment_method_id,
                customer=customer_id
            )
            
            logger.info("Payment method attached successfully", extra={
                "payment_method_id": payment_method_id,
                "customer_id": customer_id
            })
            
            return payment_method
            
        except stripe.error.StripeError as e:
            logger.error("Failed to attach payment method", exc_info=True, extra={
                "payment_method_id": payment_method_id,
                "customer_id": customer_id,
                "error": str(e)
            })
            raise

    async def set_default_payment_method(
        self,
        customer_id: str,
        payment_method_id: str
    ) -> stripe.Customer:
        """Set default payment method for customer (async)"""
        logger.info("Setting default payment method", extra={
            "customer_id": customer_id,
            "payment_method_id": payment_method_id
        })
        
        try:
            customer = await asyncio.to_thread(
                stripe.Customer.modify,
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )
            
            logger.info("Default payment method set successfully", extra={
                "customer_id": customer_id,
                "payment_method_id": payment_method_id
            })
            
            return customer
            
        except stripe.error.StripeError as e:
            logger.error("Failed to set default payment method", exc_info=True, extra={
                "customer_id": customer_id,
                "error": str(e)
            })
            raise

    async def update_subscription(
        self,
        subscription_id: str,
        new_price_id: str,
        prorate: bool = True
    ) -> stripe.Subscription:
        """Update subscription to a new plan (async)"""
        logger.info("Updating subscription", extra={
            "subscription_id": subscription_id,
            "new_price_id": new_price_id,
            "prorate": prorate
        })
        
        try:
            subscription = await asyncio.to_thread(
                stripe.Subscription.retrieve,
                subscription_id
            )
            
            subscription = await asyncio.to_thread(
                stripe.Subscription.modify,
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0].id,
                    "price": new_price_id
                }],
                proration_behavior="create_prorations" if prorate else "none"
            )
            
            logger.info("Subscription updated successfully", extra={
                "subscription_id": subscription_id,
                "new_price_id": new_price_id
            })
            
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error("Failed to update subscription", exc_info=True, extra={
                "subscription_id": subscription_id,
                "error": str(e)
            })
            raise

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a subscription (async)"""
        logger.info("Canceling subscription", extra={
            "subscription_id": subscription_id,
            "cancel_at_period_end": cancel_at_period_end
        })
        
        try:
            if cancel_at_period_end:
                subscription = await asyncio.to_thread(
                    stripe.Subscription.modify,
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = await asyncio.to_thread(
                    stripe.Subscription.cancel,
                    subscription_id
                )
            
            logger.info("Subscription canceled successfully", extra={
                "subscription_id": subscription_id,
                "cancel_at_period_end": cancel_at_period_end
            })
            
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error("Failed to cancel subscription", exc_info=True, extra={
                "subscription_id": subscription_id,
                "error": str(e)
            })
            raise

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10
    ) -> List[stripe.Invoice]:
        """List invoices for a customer (async)"""
        logger.info("Listing customer invoices", extra={
            "customer_id": customer_id,
            "limit": limit
        })
        
        try:
            invoices = await asyncio.to_thread(
                stripe.Invoice.list,
                customer=customer_id,
                limit=limit
            )
            
            logger.info("Invoices retrieved successfully", extra={
                "customer_id": customer_id,
                "invoice_count": len(invoices.data)
            })
            
            return invoices.data
            
        except stripe.error.StripeError as e:
            logger.error("Failed to list invoices", exc_info=True, extra={
                "customer_id": customer_id,
                "error": str(e)
            })
            raise

    async def get_invoice_pdf(
        self,
        invoice_id: str
    ) -> Optional[str]:
        """Get invoice PDF URL (async)"""
        logger.info("Retrieving invoice PDF", extra={
            "invoice_id": invoice_id
        })
        
        try:
            invoice = await asyncio.to_thread(
                stripe.Invoice.retrieve,
                invoice_id
            )
            pdf_url = invoice.get("invoice_pdf")
            
            logger.info("Invoice PDF retrieved", extra={
                "invoice_id": invoice_id,
                "has_pdf": pdf_url is not None
            })
            
            return pdf_url
            
        except stripe.error.StripeError as e:
            logger.error("Failed to retrieve invoice PDF", exc_info=True, extra={
                "invoice_id": invoice_id,
                "error": str(e)
            })
            raise

    async def get_upcoming_invoice(
        self,
        customer_id: str,
        subscription_id: Optional[str] = None
    ) -> Optional[stripe.Invoice]:
        """Get upcoming invoice for a customer (async)"""
        logger.info("Retrieving upcoming invoice", extra={
            "customer_id": customer_id,
            "subscription_id": subscription_id
        })
        
        try:
            params = {"customer": customer_id}
            if subscription_id:
                params["subscription"] = subscription_id
            
            invoice = await asyncio.to_thread(
                stripe.Invoice.upcoming,
                **params
            )
            
            logger.info("Upcoming invoice retrieved", extra={
                "customer_id": customer_id,
                "amount_due": invoice.amount_due
            })
            
            return invoice
            
        except stripe.error.InvalidRequestError:
            logger.info("No upcoming invoice found", extra={
                "customer_id": customer_id
            })
            return None
            
        except stripe.error.StripeError as e:
            logger.error("Failed to retrieve upcoming invoice", exc_info=True, extra={
                "customer_id": customer_id,
                "error": str(e)
            })
            raise

    async def retrieve_subscription(
        self,
        subscription_id: str
    ) -> stripe.Subscription:
        """Retrieve a subscription by ID (async)"""
        logger.info("Retrieving subscription", extra={
            "subscription_id": subscription_id
        })
        
        try:
            subscription = await asyncio.to_thread(
                stripe.Subscription.retrieve,
                subscription_id
            )
            
            logger.info("Subscription retrieved successfully", extra={
                "subscription_id": subscription_id,
                "status": subscription.status
            })
            
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error("Failed to retrieve subscription", exc_info=True, extra={
                "subscription_id": subscription_id,
                "error": str(e)
            })
            raise