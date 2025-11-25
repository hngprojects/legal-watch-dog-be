import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.users.models.roles_model import Role
from app.api.utils.permissions import ADMIN_PERMISSIONS, USER_PERMISSIONS

logger = logging.getLogger(__name__)


class RoleCRUD:
    """CRUD operations for Role model."""

    @staticmethod
    async def create_admin_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Admin",
        description: Optional[str] = "Administrator with full permissions",
    ) -> Role:
        """
        Create an admin role for an organization.

        Args:
            db: Async database session
            organization_id: UUID of the organization
            role_name: Name of the role (default: "Admin")
            description: Role description (optional)

        Returns:
            Role: Created role object

        Raises:
            Exception: If database operation fails
        """
        try:
            role = Role(
                name=role_name,
                organization_id=organization_id,
                description=description,
                permissions=ADMIN_PERMISSIONS,
            )

            db.add(role)
            await db.flush()
            await db.refresh(role)

            logger.info(
                "Created admin role: id=%s, name=%s, organization_id=%s",
                role.id,
                role.name,
                role.organization_id,
            )

            return role

        except Exception as e:
            logger.error(
                "Failed to create admin role for organization_id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to create admin role")

    async def get_default_user_role(
        db: AsyncSession,
        role_name: str = "User",
        description: Optional[str] = "LegalWatchDog User",
    ) -> Role:
        try:
            role = Role(
                name=role_name,
                description=description,
                permissions=USER_PERMISSIONS,
            )
            logger.info(
                "Created user role: id=%s, name=%s",
                role.id,
                role.name,
            )

            db.add(role)
            await db.commit()
            await db.refresh(role)
            return role

        except Exception as e:
            logger.error(
                "Failed to create user role",
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to create user role")
