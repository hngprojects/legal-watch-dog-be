import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.organization.models.user_organization_model import UserOrganization

logger = logging.getLogger(__name__)


class UserOrganizationCRUD:
    """CRUD operations for UserOrganization model."""

    @staticmethod
    async def add_user_to_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        is_active: bool = True,
    ) -> UserOrganization:
        """
        Add a user to an organization with a specific role.

        Args:
            db: Async database session
            user_id: UUID of the user
            organization_id: UUID of the organization
            role_id: UUID of the role in that organization
            is_active: Whether the membership is active

        Returns:
            UserOrganization: Created membership object

        Raises:
            ValueError: If membership already exists
            Exception: If database operation fails
        """
        try:
            existing = await UserOrganizationCRUD.get_user_organization(
                db, user_id, organization_id
            )
            if existing:
                raise ValueError("User is already a member of this organization")

            membership = UserOrganization(
                user_id=user_id,
                organization_id=organization_id,
                role_id=role_id,
                is_active=is_active,
            )

            db.add(membership)
            await db.flush()
            await db.refresh(membership)

            logger.info(
                "Added user %s to organization %s with role %s",
                user_id,
                organization_id,
                role_id,
            )

            return membership

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Failed to add user %s to organization %s: %s",
                user_id,
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to add user to organization")

    @staticmethod
    async def get_user_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Optional[UserOrganization]:
        """
        Get a specific user-organization membership.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID

        Returns:
            UserOrganization or None if not found
        """
        result = await db.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user_id,
                UserOrganization.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_organizations(
        db: AsyncSession,
        user_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[UserOrganization]:
        """
        Get all organizations a user belongs to.

        Args:
            db: Database session
            user_id: User UUID
            active_only: Only return active memberships

        Returns:
            List of UserOrganization objects
        """
        query = select(UserOrganization).where(UserOrganization.user_id == user_id)

        if active_only:
            query = query.where(UserOrganization.is_active)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_organization_users(
        db: AsyncSession,
        organization_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[UserOrganization]:
        """
        Get all users in an organization.

        Args:
            db: Database session
            organization_id: Organization UUID
            active_only: Only return active memberships

        Returns:
            List of UserOrganization objects
        """
        query = select(UserOrganization).where(UserOrganization.organization_id == organization_id)

        if active_only:
            query = query.where(UserOrganization.is_active)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_user_role_in_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        new_role_id: uuid.UUID,
    ) -> UserOrganization:
        """
        Update a user's role in an organization.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID
            new_role_id: New role UUID

        Returns:
            Updated UserOrganization object

        Raises:
            ValueError: If membership not found
        """
        membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)
        if not membership:
            raise ValueError("User membership not found in this organization")

        membership.role_id = new_role_id
        membership.updated_at = datetime.now(timezone.utc)

        db.add(membership)
        await db.flush()
        await db.refresh(membership)

        logger.info(
            "Updated user %s role to %s in organization %s",
            user_id,
            new_role_id,
            organization_id,
        )

        return membership

    @staticmethod
    async def set_membership_status(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        is_active: bool,
    ) -> UserOrganization:
        """
        Activate or deactivate a user's membership in an organization.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID
            is_active: New active status

        Returns:
            Updated UserOrganization object

        Raises:
            ValueError: If membership not found
        """
        membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)
        if not membership:
            raise ValueError("User membership not found in this organization")

        membership.is_active = is_active
        membership.updated_at = datetime.now(timezone.utc)

        db.add(membership)
        await db.flush()
        await db.refresh(membership)

        logger.info(
            "Set user %s membership status to %s in organization %s",
            user_id,
            is_active,
            organization_id,
        )

        return membership

    @staticmethod
    async def remove_user_from_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        """
        Remove a user from an organization (hard delete).

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID

        Raises:
            ValueError: If membership not found
        """
        membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)
        if not membership:
            raise ValueError("User membership not found in this organization")

        await db.delete(membership)
        await db.flush()

        logger.info(
            "Removed user %s from organization %s",
            user_id,
            organization_id,
        )
