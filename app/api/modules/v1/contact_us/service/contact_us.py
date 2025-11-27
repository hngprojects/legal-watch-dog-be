import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.contact_us.schemas.contact_us import ContactUsRequest
from app.api.modules.v1.contact_us.service.contact_us_repository import ContactUsCRUD

logger = logging.getLogger("app")


class ContactUsService:
    """
    Service class to handle contact us logic.

    """

    def __init__(self, db: AsyncSession):
        """
        Initialize contact us service.

        """

        self.db = db

    async def submit_contact_form(
        self,
        payload: ContactUsRequest,
        background_tasks: BackgroundTasks,
    ) -> dict:
        """
        Handle contact form submission.

        This method processes the contact form, sends notification emails

        Args:
            payload: Contact form data containing name, email, phone, and message
            background_tasks: FastAPI background tasks for async email sending

        Returns:
            dict: Dictionary containing the submitted email address

        Raises:
            Exception: For unexpected errors during submission process
        """
        logger.info("Processing contact form submission from email=%s", payload.email)

        try:
            admin_context = {
                "full_name": payload.full_name,
                "email": payload.email,
                "phone_number": payload.phone_number,
                "message": payload.message,
                "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }

            background_tasks.add_task(
                send_email,
                "contact_us_admin.html",
                f"New Contact Form Submission from {payload.full_name}",
                settings.ADMIN_EMAIL,
                admin_context,
            )

            user_context = {
                "full_name": payload.full_name,
                "message": payload.message,
            }

            background_tasks.add_task(
                send_email,
                "contact_us_confirmation.html",
                "We received your message",
                payload.email,
                user_context,
            )

            logger.info("Successfully processed contact form from email=%s", payload.email)

            await ContactUsCRUD.create(
                db=self.db,
                full_name=payload.full_name,
                email=payload.email,
                phone_number=payload.phone_number,
                message=payload.message,
            )

            await self.db.commit()

            return {"email": payload.email}

        except Exception as e:
            logger.error(
                "Unexpected error during contact form submission for email=%s: %s",
                payload.email,
                str(e),
                exc_info=True,
            )
            raise Exception("An error occurred while submitting your message. Please try again.")
