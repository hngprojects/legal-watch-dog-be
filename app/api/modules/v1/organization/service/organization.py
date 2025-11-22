import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.organization.models.organization_model import Organization

logger = logging.getLogger(__name__)


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
