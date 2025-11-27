# app/api/modules/v1/contact_us/repository/contact_us_repository.py
import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.contact_us.models.contact_us_model import ContactUs

logger = logging.getLogger("app")


class ContactUsCRUD:
    """CRUD operations for ContactUs model."""

    @staticmethod
    async def create(
        db: AsyncSession,
        full_name: str,
        email: str,
        phone_number: str,
        message: str,
    ) -> ContactUs:
        """
        Create a new contact us submission in the database.

        Args:
            db: Async database session
            full_name: User's full name
            email: User's email address
            phone_number: User's phone number
            message: User's message

        Returns:
            ContactUs: Created contact us object

        Raises:
            Exception: If database operation fails
        """
        try:
            contact_submission = ContactUs(
                full_name=full_name,
                email=email,
                phone_number=phone_number,
                message=message,
            )

            db.add(contact_submission)
            await db.flush()
            await db.refresh(contact_submission)

            logger.info(
                "Created contact submission: id=%s, email=%s",
                contact_submission.id,
                contact_submission.email,
            )

            return contact_submission

        except Exception as e:
            logger.error(
                "Failed to create contact submission for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to save contact submission")

    @staticmethod
    async def get_by_id(db: AsyncSession, contact_id: uuid.UUID) -> Optional[ContactUs]:
        """
        Get contact submission by ID.

        Args:
            db: Database session
            contact_id: Contact submission UUID

        Returns:
            ContactUs or None if not found
        """
        result = await db.execute(select(ContactUs).where(ContactUs.id == contact_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str, limit: int = 10) -> list[ContactUs]:
        """
        Get contact submissions by email address.

        Args:
            db: Database session
            email: Email address
            limit: Maximum number of results

        Returns:
            List of ContactUs objects
        """
        result = await db.execute(
            select(ContactUs)
            .where(ContactUs.email == email)
            .order_by(ContactUs.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
