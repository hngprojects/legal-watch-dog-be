import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.contact_us.schemas.contact_us import (
    ContactUsDetail,
    ContactUsRequest,
)
from app.api.modules.v1.contact_us.service.contact_us_repository import ContactUsCRUD
from app.api.utils.pagination import calculate_pagination

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

    async def get_all_contacts(
        self,
        page: int,
        page_size: int,
        email: Optional[str] = None,
    ) -> dict:
        """
        Get all contact submissions with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            email: Optional email filter

        Returns:
            dict: Dictionary with contacts list and pagination metadata

        Raises:
            Exception: For unexpected errors during retrieval
        """

        contacts, total_count = await ContactUsCRUD.get_all(
            db=self.db,
            page=page,
            page_size=page_size,
            email=email,
        )

        contacts_list = [ContactUsDetail.model_validate(contact) for contact in contacts]

        pagination = calculate_pagination(
            total=total_count,
            page=page,
            limit=page_size,
        )

        return {"data": contacts_list, **pagination}
