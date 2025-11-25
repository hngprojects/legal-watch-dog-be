import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.users.models.roles_model import Role  # Added import for Role
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger(__name__)


class UserCRUD:
    """CRUD operations for User model."""

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        name: str,
        hashed_password: str,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        auth_provider: str = "local",
        is_active: bool = True,
        is_verified: bool = False,  # Default to False for general users, can be overridden
    ) -> User:
        """
        Create a new user.

        Args:
            db: Async database session
            email: User email address
            name: User's full name
            hashed_password: Hashed password
            organization_id: UUID of the organization
            role_id: UUID of the user's role
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
                organization_id=organization_id,
                role_id=role_id,
                auth_provider=auth_provider,
                is_active=is_active,
                is_verified=is_verified,
            )

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                "Created user: id=%s, email=%s, organization_id=%s, role_id=%s",
                user.id,
                user.email,
                user.organization_id,
                user.role_id,
            )

            return user

        except Exception as e:
            logger.error("Failed to create user for email=%s: %s", email, str(e), exc_info=True)
            raise Exception("Failed to create user")

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
        user.updated_at = datetime.now(timezone.utc)  # Update the updated_at timestamp
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
                "Failed to create admin user for email=%s: %s", email, str(e), exc_info=True
            )
            raise Exception("Failed to create admin user")
