import asyncio
from datetime import datetime, timedelta

import nest_asyncio
from celery import shared_task
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.logger import logger
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.billing.models import (
    BillingAccount,
    BillingStatus,
    Subscription,
    SubscriptionStatus,
)
from app.api.modules.v1.organization.models import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role as RoleORM
from app.api.modules.v1.users.models.users_model import User as UserORM
from app.api.utils import send_email_background_task

# Apply nest_asyncio to allow nested event loops in Celery
nest_asyncio.apply()


def run_async_in_celery(coro):
    """
    Safely run async coroutine in Celery task.
    Handles both cases: with and without existing event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Event loop already running, use it directly
            return loop.run_until_complete(coro)
        else:
            # No running loop, use asyncio.run()
            return asyncio.run(coro)
    except RuntimeError:
        # No event loop exists, create new one
        return asyncio.run(coro)


@shared_task(name="billing.tasks.expire_trials")
def expire_trials():
    """
    Expire trials and block access for accounts with expired trials.
    Runs hourly.
    """
    return run_async_in_celery(_expire_trials_async())


async def _expire_trials_async():
    logger.info("Running trial expiration task")
    
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()

            statement = select(BillingAccount).where(
                BillingAccount.trial_ends_at <= now,
                BillingAccount.status == BillingStatus.TRIALING
            )

            result = await db.execute(statement)
            expired_accounts = result.scalars().all()

            logger.info(
                f"Found {len(expired_accounts)} expired trial accounts",
                extra={"count": len(expired_accounts)}
            )

            for billing_account in expired_accounts:
                try:
                    billing_account.status = BillingStatus.BLOCKED
                    db.add(billing_account)

                    # Call synchronous wrapper instead of async function
                    send_trial_expired_email_task(billing_account)

                    logger.info(
                        "Trial expired and account blocked",
                        extra={
                            "billing_account_id": str(billing_account.id),
                            "organization_id": str(billing_account.organization_id),
                        },
                    )

                except Exception as e:
                    logger.error(
                        "Failed to process expired trial",
                        exc_info=True,
                        extra={
                            "billing_account_id": str(billing_account.id),
                            "error": str(e)
                        },
                    )
                    continue

            await db.commit()
            logger.info("Trial expiration task completed", 
            extra={"processed": len(expired_accounts)})

        except Exception as e:
            logger.error("Trial expiration task failed", exc_info=True, extra={"error": str(e)})
            await db.rollback()


@shared_task(name="billing.tasks.update_billing_status")
def update_billing_status():
    """
    Update billing status based on subscription period.
    Fallback if webhook fails.
    Runs every 6 hours.
    """
    return run_async_in_celery(_update_billing_status_async())


async def _update_billing_status_async():
    """Async implementation of update_billing_status"""
    logger.info("Running billing status update task")
    
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()

            # Get all billing accounts with subscriptions
            statement = select(BillingAccount).where(
                BillingAccount.stripe_subscription_id.isnot(None)
            )
            result = await db.execute(statement)
            billing_accounts = result.scalars().all()

            logger.info(
                f"Checking {len(billing_accounts)} billing accounts",
                extra={"count": len(billing_accounts)}
            )

            for billing_account in billing_accounts:
                try:
                    # Get active subscription
                    sub_statement = select(Subscription).where(
                        Subscription.billing_account_id == billing_account.id,
                        Subscription.is_active 
                    ).order_by(Subscription.created_at.desc())
                    
                    sub_result = await db.execute(sub_statement)
                    subscription = sub_result.scalars().first()

                    if not subscription:
                        continue

                    # Map Stripe subscription status to billing status
                    mapped_status = _map_subscription_status(subscription.status)

                    # Check if period has ended
                    if subscription.current_period_end < now:
                        if subscription.cancel_at_period_end:
                            mapped_status = BillingStatus.CANCELLED
                            subscription.is_active = False
                        elif subscription.status != SubscriptionStatus.ACTIVE:
                            mapped_status = BillingStatus.PAST_DUE

                    # Update billing account if status changed
                    if billing_account.status != mapped_status:
                        old_status = billing_account.status
                        billing_account.status = mapped_status
                        
                        # Update period dates
                        billing_account.current_period_start = subscription.current_period_start
                        billing_account.current_period_end = subscription.current_period_end
                        
                        db.add(billing_account)

                        logger.info(
                            "Billing status updated",
                            extra={
                                "billing_account_id": str(billing_account.id),
                                "old_status": old_status.value,
                                "new_status": mapped_status.value,
                            },
                        )

                        # Send notification if moved to past_due or blocked
                        if mapped_status in [BillingStatus.PAST_DUE, BillingStatus.BLOCKED]:
                            # Call synchronous wrapper instead of async function
                            send_payment_failed_email_task(billing_account)

                except Exception as e:
                    logger.error(
                        "Failed to update billing status",
                        exc_info=True,
                        extra={"billing_account_id": str(billing_account.id), "error": str(e)},
                    )
                    continue

            await db.commit()
            logger.info("Billing status update task completed")

        except Exception as e:
            logger.error("Billing status update task failed",
             exc_info=True, extra={"error": str(e)})
            await db.rollback()


@shared_task(name="billing.tasks.send_trial_reminders")
def send_trial_reminders():
    """
    Send trial reminder emails at 3 days and 1 day before expiry.
    Runs daily at 9 AM UTC.
    """
    return run_async_in_celery(_send_trial_reminders_async())


async def _send_trial_reminders_async():
    """Async implementation of send_trial_reminders"""
    logger.info("Running trial reminder task")
    
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()

            # 3-day reminder
            three_days_from_now = now + timedelta(days=3)
            statement_3d = select(BillingAccount).where(
                BillingAccount.trial_ends_at >= now,
                BillingAccount.trial_ends_at <= three_days_from_now,
                BillingAccount.status == BillingStatus.TRIALING,
            )
            result_3d = await db.execute(statement_3d)
            accounts_3d = result_3d.scalars().all()

            for billing_account in accounts_3d:
                days_remaining = (billing_account.trial_ends_at - now).days

                if days_remaining == 3:
                    # Call synchronous wrapper instead of async function
                    send_trial_reminder_email_task(billing_account, days_remaining=3)
                    logger.info(
                        "Sent 3-day trial reminder",
                        extra={"billing_account_id": str(billing_account.id)},
                    )

            # 1-day reminder
            one_day_from_now = now + timedelta(days=1)
            statement_1d = select(BillingAccount).where(
                BillingAccount.trial_ends_at >= now,
                BillingAccount.trial_ends_at <= one_day_from_now,
                BillingAccount.status == BillingStatus.TRIALING,
            )
            result_1d = await db.execute(statement_1d)
            accounts_1d = result_1d.scalars().all()

            for billing_account in accounts_1d:
                days_remaining = (billing_account.trial_ends_at - now).days

                if days_remaining == 1:
                    # Call synchronous wrapper instead of async function
                    send_trial_reminder_email_task(billing_account, days_remaining=1)
                    logger.info(
                        "Sent 1-day trial reminder",
                        extra={"billing_account_id": str(billing_account.id)},
                    )

            logger.info(
                "Trial reminder task completed",
                extra={"sent_3d": len(accounts_3d), "sent_1d": len(accounts_1d)},
            )

        except Exception as e:
            logger.error("Trial reminder task failed", exc_info=True, extra={"error": str(e)})


# ==================== HELPER FUNCTIONS ====================

def _map_subscription_status(stripe_status: SubscriptionStatus) -> BillingStatus:
    """Map Stripe subscription status to BillingStatus"""
    if stripe_status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
        return BillingStatus.ACTIVE
    elif stripe_status == SubscriptionStatus.PAST_DUE:
        return BillingStatus.PAST_DUE
    elif stripe_status in [SubscriptionStatus.INCOMPLETE,
     SubscriptionStatus.INCOMPLETE_EXPIRED,
      SubscriptionStatus.UNPAID]:
        return BillingStatus.UNPAID
    elif stripe_status in [SubscriptionStatus.CANCELED]:
        return BillingStatus.CANCELLED
    else:
        return BillingStatus.BLOCKED


# ==================== EMAIL TASK WRAPPERS ====================

def send_trial_expired_email_task(billing_account: BillingAccount):
    """
    Synchronous wrapper for _send_trial_expired_email_async.
    Creates a fresh event loop for Celery compatibility.
    """
    run_async_in_celery(_send_trial_expired_email_async(billing_account))


def send_trial_reminder_email_task(billing_account: BillingAccount, days_remaining: int):
    """
    Synchronous wrapper for _send_trial_reminder_email_async.
    Creates a fresh event loop for Celery compatibility.
    """
    run_async_in_celery(_send_trial_reminder_email_async(billing_account, days_remaining))


def send_payment_failed_email_task(billing_account: BillingAccount):
    """
    Synchronous wrapper for _send_payment_failed_email_async.
    Creates a fresh event loop for Celery compatibility.
    """
    run_async_in_celery(_send_payment_failed_email_async(billing_account))


# ==================== ASYNC EMAIL IMPLEMENTATIONS ====================

async def _send_trial_expired_email_async(billing_account: BillingAccount):
    """
    Send trial expired notification.

    Note: Uses synchronous Celery .delay() - do NOT await this call.
    The email task runs in a separate Celery worker.
    """
    try:
        # Use a fresh session to avoid concurrent operation errors
        async with AsyncSessionLocal() as db:
            org = await db.get(Organization, billing_account.organization_id)
            if not org:
                return

            # Join User -> UserOrganization -> Role (required)
            admin_statement = (
                select(UserORM)
                .join(UserOrganization, UserOrganization.user_id == UserORM.id)
                .join(RoleORM, RoleORM.id == UserOrganization.role_id)
                .where(
                    UserOrganization.organization_id == org.id,
                    RoleORM.name.in_(["admin", "owner"])
                )
            )

            result = await db.execute(admin_statement)
            admins = result.scalars().all()

            for admin in admins:
                # Synchronous Celery task - do NOT await
                send_email_background_task.delay(
                    to_email=admin.email,
                    subject="Your Legal Watchdog Trial Has Expired",
                    template_name="trial_expired",
                    context={
                        "user_name": admin.name or admin.email,
                        "organization_name": org.name,
                        "billing_url": f"{settings.FRONTEND_URL}/billing",
                    },
                )

    except Exception as e:
        logger.error(
            "Failed to send trial expired email",
            exc_info=True,
            extra={
                "billing_account_id": str(billing_account.id),
                "error": str(e)
            },
        )


async def _send_trial_reminder_email_async(billing_account: BillingAccount, days_remaining: int):
    """
    Send trial reminder email.

    Note: Uses synchronous Celery .delay() - do NOT await this call.
    The email task runs in a separate Celery worker.
    """
    try:
        # Use a fresh session to avoid concurrent operation errors
        async with AsyncSessionLocal() as db:
            org = await db.get(Organization, billing_account.organization_id)
            if not org:
                return

            # Join User -> UserOrganization -> Role
            admin_statement = (
                select(UserORM)
                .join(UserOrganization, UserOrganization.user_id == UserORM.id)
                .join(RoleORM, RoleORM.id == UserOrganization.role_id)
                .where(
                    UserOrganization.organization_id == org.id,
                    RoleORM.name.in_(["admin", "owner"])
                )
            )

            result = await db.execute(admin_statement)
            admins = result.scalars().all()

            for admin in admins:
                # Synchronous Celery task - do NOT await
                send_email_background_task.delay(
                    to_email=admin.email,
                    subject=(
                        f"Your Legal Watchdog Trial Ends in {days_remaining} "
                        f"Day{'s' if days_remaining > 1 else ''}"
                    ),

                    template_name="trial_reminder",
                    context={
                        "user_name": admin.name or admin.email,
                        "organization_name": org.name,
                        "days_remaining": days_remaining,
                        "trial_ends_at": billing_account.trial_ends_at.strftime("%B %d, %Y"),
                        "billing_url": f"{settings.FRONTEND_URL}/billing",
                    },
                )

    except Exception as e:
        logger.error(
            "Failed to send trial reminder email",
            exc_info=True,
            extra={"billing_account_id": str(billing_account.id), "error": str(e)},
        )


async def _send_payment_failed_email_async(billing_account: BillingAccount):
    """
    Send payment failure notification.

    Note: Uses synchronous Celery .delay() - do NOT await this call.
    The email task runs in a separate Celery worker.
    """
    try:
        # Use a fresh session to avoid concurrent operation errors
        async with AsyncSessionLocal() as db:
            org = await db.get(Organization, billing_account.organization_id)
            if not org:
                return

            # Join User -> UserOrganization -> Role
            admin_statement = (
                select(UserORM)
                .join(UserOrganization, UserOrganization.user_id == UserORM.id)
                .join(RoleORM, RoleORM.id == UserOrganization.role_id)
                .where(
                    UserOrganization.organization_id == org.id,
                    RoleORM.name.in_(["admin", "owner"])
                )
            )

            result = await db.execute(admin_statement)
            admins = result.scalars().all()

            for admin in admins:
                # Synchronous Celery task - do NOT await
                send_email_background_task.delay(
                    to_email=admin.email,
                    subject="Payment Failed - Action Required",
                    template_name="payment_failed",
                    context={
                        "user_name": admin.name or admin.email,
                        "organization_name": org.name,
                        "billing_url": f"{settings.FRONTEND_URL}/billing",
                    },
                )

    except Exception as e:
        logger.error(
            "Failed to send payment failed email",
            exc_info=True,
            extra={"billing_account_id": str(billing_account.id), "error": str(e)},
        )