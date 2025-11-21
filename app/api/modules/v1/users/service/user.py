import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger(__name__)


class UserCRUD:
    """CRUD operations for User model."""

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
