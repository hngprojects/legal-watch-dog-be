import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.utils.get_organization_by_email import get_organization_by_email
from app.api.utils.redis import get_organization_credentials

logger = logging.getLogger(__name__)


async def validate_organization_email_available(db: AsyncSession, email: str) -> None:
    """
    Validate that an organization email is not already registered.

    Args:
        db: Database session for querying
        email: Email address to check

    Raises:
        ValueError: If organization with email already exists
    """
    existing_org = await get_organization_by_email(db, email)
    logger.debug("Organization existence check for email=%s: %s", email, bool(existing_org))

    if existing_org:
        logger.warning("Validation failed: Organization already exists with email=%s", email)
        raise ValueError("An organization with this email already exists.")


async def validate_no_pending_registration(redis_client: Redis, email: str) -> None:
    """
    Validate that there is no pending registration for the email.

    Args:
        redis_client: Redis client instance
        email: Email address to check for pending registration

    Raises:
        ValueError: If a pending registration exists for this email
    """
    pending = await get_organization_credentials(redis_client, email)

    if pending:
        logger.warning("Validation failed: Pending registration exists for email=%s", email)
        raise ValueError("A registration with this email is already pending OTP verification.")
