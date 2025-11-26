import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.organization.models.organization_model import Organization

logger = logging.getLogger("app")


class OrganizationCRUD:
    """CRUD operations for Organization model."""

    @staticmethod
    async def create_organization(
        db: AsyncSession, name: str, industry: Optional[str] = None
    ) -> Organization:
        """
        Create a new organization in the database.

        Args:
            db: Async database session
            name: Organization name
            industry: Industry type (optional)

        Returns:
            Organization: Created organization object

        Raises:
            Exception: If database operation fails
        """
        try:
            organization = Organization(name=name, industry=industry, is_active=True)

            db.add(organization)
            await db.flush()
            await db.refresh(organization)

            logger.info("Created organization: id=%s, name=%s", organization.id, organization.name)

            return organization

        except Exception as e:
            logger.error(
                "Failed to create organization with name=%s: %s", name, str(e), exc_info=True
            )
            raise Exception("Failed to create organization")

    @staticmethod
    async def get_by_id(db: AsyncSession, organization_id: uuid.UUID) -> Optional[Organization]:
        """
        Get organization by ID.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            Organization or None if not found
        """
        result = await db.execute(select(Organization).where(Organization.id == organization_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[Organization]:
        """
        Get organization by name.

        Args:
            db: Database session
            name: Organization name

        Returns:
            Organization or None if not found
        """
        result = await db.execute(select(Organization).where(Organization.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession,
        organization_id: uuid.UUID,
        name: str | None = None,
        industry: str | None = None,
        is_active: bool | None = None,
    ) -> Organization:
        """
        Update organization details.

        Args:
            db: Database session
            organization_id: Organization UUID
            name: Optional new organization name
            industry: Optional new industry
            is_active: Optional new active status

        Returns:
            Organization: Updated organization object

        Raises:
            Exception: If database operation fails
        """
        from datetime import datetime, timezone

        try:
            result = await db.execute(
                select(Organization).where(Organization.id == organization_id)
            )
            organization = result.scalar_one_or_none()

            if not organization:
                raise ValueError("Organization not found")

            if name is not None:
                organization.name = name
            if industry is not None:
                organization.industry = industry
            if is_active is not None:
                organization.is_active = is_active

            organization.updated_at = datetime.now(timezone.utc)

            await db.flush()
            await db.refresh(organization)

            logger.info("Updated organization: id=%s, name=%s", organization.id, organization.name)

            return organization

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update organization with id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to update organization")
