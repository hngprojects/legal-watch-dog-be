from datetime import datetime, timedelta

from celery import shared_task
from sqlmodel import Session, select

from app.api.core.config import settings
from app.api.core.logger import logger
from app.api.db.session import SessionLocal
from app.api.modules.v1.billing.models import BillingAccount
from app.api.modules.v1.organization.models import Organization
from app.api.modules.v1.users.models import User
from app.api.utils.email import send_email_background_task


@shared_task(name="billing.tasks.expire_trials")
def expire_trials():
    """
    Celery Beat task to expire trials and block access.
    Runs hourly or daily.
    
    - Finds all billing accounts where trial has expired
    - Sets status to 'blocked' if no active subscription
    - Sends notification emails to org admins
    """
    logger.info("Running trial expiration task")
    
    db = SessionLocal()
    
    try:
        now = datetime.utcnow()
        
        # Find all billing accounts with expired trials and no active subscription
        statement = select(BillingAccount).where(
            BillingAccount.trial_ends_at <= now,
            BillingAccount.status == "trialing"
        )
        
        expired_accounts = db.exec(statement).all()
        
        logger.info(f"Found {len(expired_accounts)} expired trial accounts", extra={
            "count": len(expired_accounts)
        })
        
        for billing_account in expired_accounts:
            try:
                # Update status to blocked
                billing_account.status = "blocked"
                billing_account.blocked_at = now
                db.add(billing_account)
                
                # Send notification email to org admins
                _send_trial_expired_email(db, billing_account)
                
                logger.info("Trial expired and account blocked", extra={
                    "billing_account_id": str(billing_account.id),
                    "organization_id": str(billing_account.organization_id)
                })
            
            except Exception as e:
                logger.error("Failed to process expired trial", exc_info=True, extra={
                    "billing_account_id": str(billing_account.id),
                    "error": str(e)
                })
                continue
        
        db.commit()
        
        logger.info("Trial expiration task completed", extra={
            "processed": len(expired_accounts)
        })
    
    except Exception as e:
        logger.error("Trial expiration task failed", exc_info=True, extra={
            "error": str(e)
        })
        db.rollback()
    
    finally:
        db.close()

@shared_task(name="billing.tasks.send_trial_reminders")
def send_trial_reminders():
    """
    Celery Beat task to send trial reminder emails.
    Runs daily.
    
    Sends reminders:
    - 3 days before trial ends
    - 1 day before trial ends
    """
    logger.info("Running trial reminder task")
    
    db = SessionLocal()
    
    try:
        now = datetime.utcnow()
        
        # 3-day reminder
        three_days_from_now = now + timedelta(days=3)
        statement_3d = select(BillingAccount).where(
            BillingAccount.trial_ends_at >= now,
            BillingAccount.trial_ends_at <= three_days_from_now,
            BillingAccount.status == "trialing"
        )
        accounts_3d = db.exec(statement_3d).all()
        
        for billing_account in accounts_3d:
            days_remaining = (billing_account.trial_ends_at - now).days
            
            if days_remaining == 3:
                _send_trial_reminder_email(db, billing_account, days_remaining=3)
                logger.info("Sent 3-day trial reminder", extra={
                    "billing_account_id": str(billing_account.id)
                })
        
        # 1-day reminder
        one_day_from_now = now + timedelta(days=1)
        statement_1d = select(BillingAccount).where(
            BillingAccount.trial_ends_at >= now,
            BillingAccount.trial_ends_at <= one_day_from_now,
            BillingAccount.status == "trialing"
        )
        accounts_1d = db.exec(statement_1d).all()
        
        for billing_account in accounts_1d:
            days_remaining = (billing_account.trial_ends_at - now).days
            
            if days_remaining == 1:
                _send_trial_reminder_email(db, billing_account, days_remaining=1)
                logger.info("Sent 1-day trial reminder", extra={
                    "billing_account_id": str(billing_account.id)
                })
        
        logger.info("Trial reminder task completed", extra={
            "sent_3d": len(accounts_3d),
            "sent_1d": len(accounts_1d)
        })
    
    except Exception as e:
        logger.error("Trial reminder task failed", exc_info=True, extra={
            "error": str(e)
        })
    
    finally:
        db.close()

def _send_trial_expired_email(db: Session, billing_account: BillingAccount):
    """Send trial expired notification to org admins"""
    try:
        # Get organization
        org = db.get(Organization, billing_account.organization_id)
        if not org:
            return
        
        # Get admin users
        admin_statement = select(User).where(
            User.organization_id == org.id,
            User.role.in_(["admin", "owner"])
        )
        admins = db.exec(admin_statement).all()
        
        for admin in admins:
            send_email_background_task.delay(
                to_email=admin.email,
                subject="Your Legal Watchdog Trial Has Expired",
                template_name="trial_expired",
                context={
                    "user_name": admin.full_name or admin.email,
                    "organization_name": org.name,
                    "billing_url": f"{settings.FRONTEND_URL}/billing"
                }
            )
    
    except Exception as e:
        logger.error("Failed to send trial expired email", exc_info=True, extra={
            "billing_account_id": str(billing_account.id),
            "error": str(e)
        })

def _send_trial_reminder_email(db: Session, billing_account: BillingAccount, days_remaining: int):
    """Send trial reminder email to org admins"""
    try:
        # Get organization
        org = db.get(Organization, billing_account.organization_id)
        if not org:
            return
        
        # Get admin users
        admin_statement = select(User).where(
            User.organization_id == org.id,
            User.role.in_(["admin", "owner"])
        )
        admins = db.exec(admin_statement).all()
        
        for admin in admins:
            send_email_background_task.delay(
                to_email=admin.email,
                subject=(
                    f"Your Legal Watchdog Trial Ends in {days_remaining} "
                    f"Day{'s' if days_remaining > 1 else ''}"
                ),
                template_name="trial_reminder",
                context={
                    "user_name": admin.full_name or admin.email,
                    "organization_name": org.name,
                    "days_remaining": days_remaining,
                    "trial_ends_at": billing_account.trial_ends_at.strftime("%B %d, %Y"),
                    "billing_url": f"{settings.FRONTEND_URL}/billing"
                }
            )

    
    except Exception as e:
        logger.error("Failed to send trial reminder email", exc_info=True, extra={
            "billing_account_id": str(billing_account.id),
            "error": str(e)
        })