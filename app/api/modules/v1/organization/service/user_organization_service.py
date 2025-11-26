import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User

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
    async def get_all_user_organizations(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        active_only: bool = True,
    ) -> dict:
        """
        Get paginated organizations a user belongs to with database-level pagination.

        Args:
            db: Database session
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Only return active memberships

        Returns:
            Dictionary with organizations list and total count
        """
        membership_query = select(UserOrganization).where(UserOrganization.user_id == user_id)

        if active_only:
            membership_query = membership_query.where(UserOrganization.is_active)

        count_query = (
            sa_select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.user_id == user_id)
        )
        if active_only:
            count_query = count_query.where(UserOrganization.is_active)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        membership_query = membership_query.offset(skip).limit(limit)
        memberships_result = await db.execute(membership_query)
        memberships = list(memberships_result.scalars().all())

        organizations = []
        for membership in memberships:
            org_result = await db.execute(
                select(Organization).where(Organization.id == membership.organization_id)
            )
            org = org_result.scalar_one_or_none()

            if not org:
                continue

            role = await db.get(Role, membership.role_id)

            organizations.append(
                {
                    "organization_id": str(org.id),
                    "name": org.name,
                    "industry": org.industry,
                    "is_active": org.is_active,
                    "user_role": role.name if role else None,
                    "created_at": org.created_at.isoformat(),
                    "updated_at": org.updated_at.isoformat(),
                }
            )

        return {"organizations": organizations, "total": total}

    @staticmethod
    async def get_all_users_in_organization(
        db: AsyncSession,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        active_only: bool = True,
    ) -> dict:
        """
        Get paginated users in an organization with their details.

        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Only return active memberships

        Returns:
            Dictionary with users list and total count
        """

        membership_query = select(UserOrganization).where(
            UserOrganization.organization_id == organization_id
        )

        if active_only:
            membership_query = membership_query.where(UserOrganization.is_active)

        count_query = (
            sa_select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.organization_id == organization_id)
        )
        if active_only:
            count_query = count_query.where(UserOrganization.is_active)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        membership_query = membership_query.offset(skip).limit(limit)
        memberships_result = await db.execute(membership_query)
        memberships = list(memberships_result.scalars().all())

        users = []
        for membership in memberships:
            user_result = await db.execute(select(User).where(User.id == membership.user_id))
            user = user_result.scalar_one_or_none()

            if not user:
                continue

            role = await db.get(Role, membership.role_id)

            users.append(
                {
                    "user_id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "role": role.name if role else None,
                    "role_id": str(role.id) if role else None,
                    "membership_active": membership.is_active,
                    "joined_at": membership.joined_at.isoformat(),
                    "created_at": user.created_at.isoformat(),
                }
            )

        return {"users": users, "total": total}

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
