import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


class UserCRUD:
    """CRUD operations for User model."""

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        name: str,
        hashed_password: str,
        auth_provider: str = "local",
        is_active: bool = True,
        is_verified: bool = False,
    ) -> User:
        """
        Create a new user.

        Args:
            db: Async database session
            email: User email address
            name: User's full name
            hashed_password: Hashed password
            auth_provider: Authentication provider (default: "local")
            is_active: Whether the user account is active (default: True)
            is_verified: Whether the user's email is verified (default: False)

        Returns:
            User: Created user object

        Raises:
            Exception: If database operation fails
        """
        try:
            user = User(
                email=email,
                name=name,
                hashed_password=hashed_password,
                auth_provider=auth_provider,
                is_active=is_active,
                is_verified=is_verified,
            )

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                "Created user: id=%s, email=%s",
                user.id,
                user.email,
            )

            return user

        except Exception as e:
            logger.error("Failed to create user for email=%s: %s", email, str(e), exc_info=True)
            raise Exception("Failed to create user")

    @staticmethod
    async def create_google_user(
        db: AsyncSession,
        email: str,
        name: str,
    ) -> User:
        """
        Create a new Google OAuth user.

        Args:
            db: Async database session
            email: User email address
            name: User's full name

        Returns:
            User: Created Google-authenticated user object

        Raises:
            Exception: If database operation fails
        """
        try:
            user = User(
                email=email,
                name=name,
                hashed_password=None,
                auth_provider="google",
                is_active=True,
                is_verified=True,
            )

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                "Created Google OAuth user: id=%s, email=%s",
                user.id,
                user.email,
            )

            return user

        except Exception as e:
            logger.error(
                "Failed to create Google OAuth user for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to create Google user")

    @staticmethod
    async def set_user_active_status(db: AsyncSession, user_id: uuid.UUID, is_active: bool) -> User:
        """
        Set a user's active status.

        Args:
            db: Async database session
            user_id: UUID of the user to update
            is_active: The new active status (True for active, False for deactivated)

        Returns:
            User: The updated user object

        Raises:
            ValueError: If the user is not found
            Exception: If database operation fails
        """
        user = await db.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        user.is_active = is_active
        user.updated_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info("User %s active status set to %s", user_id, is_active)
        return user

    @staticmethod
    async def update_user_role(
        db: AsyncSession, user_id: uuid.UUID, new_role_id: uuid.UUID
    ) -> User:
        """
        Update a user's role.

        Args:
            db: Async database session
            user_id: UUID of the user to update
            new_role_id: UUID of the new role to assign

        Returns:
            User: The updated user object

        Raises:
            ValueError: If the user or new role is not found
            Exception: If database operation fails
        """
        user = await db.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        new_role = await db.get(Role, new_role_id)
        if not new_role:
            raise ValueError(f"Role with ID {new_role_id} not found.")

        if user.organization_id != new_role.organization_id:
            raise ValueError("Cannot assign a role from a different organization.")

        user.role_id = new_role_id
        user.updated_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info("User %s role updated to %s", user_id, new_role_id)
        return user

    @staticmethod
    async def create_admin_user(
        db: AsyncSession,
        email: str,
        name: str,
        hashed_password: str,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        auth_provider: str = "local",
    ) -> User:
        """
        Create an admin user for an organization.

        Args:
            db: Async database session
            email: User email address
            name: User's full name
            hashed_password: Hashed password
            organization_id: UUID of the organization
            role_id: UUID of the admin role
            auth_provider: Authentication provider (default: "local")

        Returns:
            User: Created user object

        Raises:
            Exception: If database operation fails
        """
        try:
            user = User(
                email=email,
                name=name,
                hashed_password=hashed_password,
                organization_id=organization_id,
                role_id=role_id,
                auth_provider=auth_provider,
                is_active=True,
                is_verified=True,
            )

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                "Created admin user: id=%s, email=%s, organization_id=%s",
                user.id,
                user.email,
                user.organization_id,
            )

            return user

        except Exception as e:
            logger.error(
                "Failed to create admin user for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to create admin user")

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str):
        """
        Get user by email.

        Args:
            db: Database session
            email: User email address

        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_organization_and_role(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> User:
        """
        Update user's organization and role.

        This is used when a user creates an organization and becomes its admin.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID
            role_id: Role UUID

        Returns:
            Updated user instance

        Raises:
            ValueError: If user not found
        """
        user = await UserCRUD.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")

        user.organization_id = organization_id
        user.role_id = role_id
        user.updated_at = datetime.now(timezone.utc)

        db.add(user)
        await db.flush()
        await db.refresh(user)

        logger.info(f"Updated user {user_id}: organization_id={organization_id}, role_id={role_id}")

        return user

    @staticmethod
    async def update_user(db: AsyncSession, user_id: uuid.UUID, **kwargs) -> User:
        """
        Update user fields.

        Args:
            db: Database session
            user_id: User UUID
            **kwargs: Fields to update

        Returns:
            Updated user instance

        Raises:
            ValueError: If user not found
        """
        user = await UserCRUD.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")

        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        user.updated_at = datetime.now(timezone.utc)
        db.add(user)
        await db.flush()
        await db.refresh(user)

        logger.info(f"Updated user {user_id}: {kwargs}")
        return user

    @staticmethod
    async def get_user_profile(db: AsyncSession, user_id: uuid.UUID) -> dict:
        """
        Fetches user, memberships, organizations, and roles

        """

        from app.api.modules.v1.organization.models.organization_model import Organization
        from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
        from app.api.modules.v1.users.models.roles_model import Role

        logger.info(f"Fetching optimized profile for user_id={user_id}")

        try:
            user = await UserCRUD.get_by_id(db, user_id)
            if not user:
                raise ValueError("User not found")

            stmt = (
                select(UserOrganization, Organization, Role)
                .join(Organization, Organization.id == UserOrganization.organization_id)
                .join(Role, Role.id == UserOrganization.role_id, isouter=True)
                .where(UserOrganization.user_id == user_id)
            )

            result = await db.execute(stmt)
            rows = result.all()

            organizations = []
            for membership, org, role in rows:
                organizations.append(
                    {
                        "organization_id": str(org.id),
                        "name": org.name,
                        "industry": org.industry,
                        "is_active": org.is_active,
                        "membership_active": membership.is_active,
                        "role": {
                            "id": str(role.id) if role else None,
                            "name": role.name if role else None,
                            "permissions": role.permissions if role else {},
                        },
                        "joined_at": membership.created_at.isoformat(),
                        "membership_updated_at": membership.updated_at.isoformat()
                        if membership.updated_at
                        else None,
                    }
                )

            profile = {
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "auth_provider": user.auth_provider,
                    "profile_picture_url": user.profile_picture_url,
                    "provider_user_id": user.provider_user_id,
                    "provider_profile_data": user.provider_profile_data,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                },
                "organizations": organizations,
                "statistics": {
                    "total_organizations": len(organizations),
                    "active_memberships": sum(
                        1 for org in organizations if org["membership_active"]
                    ),
                    "admin_roles": sum(
                        1
                        for org in organizations
                        if org["role"]["name"] == "Admin"
                        or org["role"]["permissions"].get("manage_organization", False)
                    ),
                },
            }

            logger.info(f"Successfully retrieved profile (optimized) for user_id={user_id}")
            return profile

        except Exception as e:
            logger.error(
                f"Error fetching optimized profile for user_id={user_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve user profile")
