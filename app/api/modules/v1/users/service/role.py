import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.users.models.roles_model import Role
from app.api.utils.permissions import ADMIN_PERMISSIONS, MANAGER_PERMISSIONS, USER_PERMISSIONS

logger = logging.getLogger("app")


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

    @staticmethod
    async def create_owner_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Owner",
        description: Optional[str] = "Owner with full permissions",
    ) -> Role:
        """
        Create an owner role for an organization.

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
                "Created owner role: id=%s, name=%s, organization_id=%s",
                role.id,
                role.name,
                role.organization_id,
            )

            return role

        except Exception as e:
            logger.error(
                "Failed to create owner role for organization_id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to create owner role")

    @staticmethod
    async def get_default_user_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Member",
        description: Optional[str] = "Organization Member with basic permissions",
    ) -> Role:
        """
        Get or create a default user role for an organization.

        This function retrieves an existing 'Member' role for a given organization.
        If it doesn't exist, it creates a new one with predefined user permissions.

        Args:
            db (AsyncSession): The active database session.
            organization_id: UUID of the organization for which to get/create the role.
            role_name (str, optional): Name of the role to get or create. Defaults to "Member".
            description (str, optional): Description of the role. Defaults to
            "Organization Member with basic permissions".

        Returns:
            Role: The existing or newly created role instance.

        Raises:
            Exception: If the role creation or database operation fails.
        """

        try:
            existing_role = await RoleCRUD.get_role_by_name_and_organization(
                db, role_name, organization_id
            )

            if existing_role:
                logger.info(
                    "Retrieved existing user role: id=%s, name=%s, organization_id=%s",
                    existing_role.id,
                    existing_role.name,
                    existing_role.organization_id,
                )
                return existing_role

            role = Role(
                name=role_name,
                organization_id=organization_id,
                description=description,
                permissions=USER_PERMISSIONS,
            )
            logger.info(
                "Created user role: id=%s, name=%s, organization_id=%s",
                role.id,
                role.name,
                role.organization_id,
            )

            db.add(role)
            await db.flush()
            await db.refresh(role)
            return role

        except Exception as e:
            logger.error(
                "Failed to get or create user role for organization_id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to get or create user role")

    @staticmethod
    async def create_manager_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Manager",
        description: Optional[str] = "Team manager with elevated project management permissions",
    ) -> Role:
        """
        Create a manager role for an organization.

        Args:
            db: Async database session
            organization_id: UUID of the organization
            role_name: Name of the role (default: "Manager")
            description: Role description (optional)

        Returns:
            Role: Created role object

        Raises:
            Exception: If database operation fails
        """
        try:
            existing_role = await RoleCRUD.get_role_by_name_and_organization(
                db, role_name, organization_id
            )
            if existing_role:
                logger.info(
                    "Manager role already exists: id=%s, name=%s, organization_id=%s",
                    existing_role.id,
                    existing_role.name,
                    existing_role.organization_id,
                )
                return existing_role

            role = Role(
                name=role_name,
                organization_id=organization_id,
                description=description,
                permissions=MANAGER_PERMISSIONS,
            )

            db.add(role)
            await db.flush()
            await db.refresh(role)

            logger.info(
                "Created manager role: id=%s, name=%s, organization_id=%s",
                role.id,
                role.name,
                role.organization_id,
            )

            return role

        except Exception as e:
            logger.error(
                "Failed to create manager role for organization_id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to create manager role")

    @staticmethod
    async def get_role_by_name_and_organization(
        db: AsyncSession, role_name: str, organization_id: uuid.UUID
    ) -> Optional[Role]:
        """Get role by name and organization."""
        try:
            result = await db.execute(
                select(Role).where(Role.name == role_name, Role.organization_id == organization_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"Error fetching role by name={role_name} for org={organization_id}: {str(e)}"
            )
            raise Exception("Failed to get role")
