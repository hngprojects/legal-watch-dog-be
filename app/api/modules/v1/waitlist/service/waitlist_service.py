import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.waitlist.models.waitlist_model import Waitlist
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)

logger = logging.getLogger("app")


class WaitlistService:
    """Business logic for waitlist operations"""

    async def add_to_waitlist(
        self,
        db: AsyncSession,
        waitlist_data: WaitlistSignup,
    ) -> WaitlistResponse:
        """
        Add an email to the waitlist.

        Handles:
        - Email validation
        - Duplicate checking
        - Database insertion
        - Email notification
        - Logging
        """
        organization_email = waitlist_data.organization_email.lower().strip()
        organization_name = waitlist_data.organization_name.strip()

        # Check if exists
        if await self._email_exists(db, organization_email):
            logger.warning(f"Attempted duplicate signup: {organization_email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered on waitlist",
            )

        try:
            # Create entry
            new_entry = Waitlist(
                organization_email=organization_email,
                organization_name=organization_name,
            )
            db.add(new_entry)
            await db.commit()

            logger.info(f"Successfully added to database: {organization_email}")

            await self._send_confirmation_email(waitlist_data)

            self._log_signup(organization_email)

            return WaitlistResponse(
                success=True,
                message="Successfully added to waitlist.",
                organization_email=organization_email,
                organization_name=organization_name,
            )

        except Exception as e:
            await db.rollback()  # ✅ Rollback on any error
            logger.error(f"Failed to add to waitlist: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process waitlist signup",
            )

    async def _email_exists(self, db: AsyncSession, email: str) -> bool:
        """Check if email already exists"""
        stmt = select(Waitlist).where(Waitlist.organization_email == email.lower())
        result = await db.execute(stmt)
        exists = result.scalar_one_or_none() is not None
        if exists:
            logger.debug(f"Email found in database: {email}")
        return exists

    async def _send_confirmation_email(self, email_data: WaitlistSignup):
        """Send waitlist confirmation email"""
        try:
            context = {
                "organization_name": email_data.organization_name,
                "organization_email": email_data.organization_email,
            }
            await send_email(
                template_name="waitlist.html",
                subject="You're on the Waitlist for Legal Watchdog!",
                recipient=email_data.organization_email,
                context=context,
            )
            logger.info(f"Waitlist email sent successfully to {email_data.organization_email}")
        except Exception as e:
            logger.error(
                f"Failed to send email to {email_data.organization_email}:{str(e)}",
                exc_info=True,
            )

    def _log_signup(self, email: str):
        """Log the signup event"""
        logger.info(f"New waitlist signup: {email}")


waitlist_service = WaitlistService()
