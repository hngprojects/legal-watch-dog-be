import logging

from app.api.core.dependencies.redis_service import add_token_to_denylist
from app.api.core.logger import setup_logging
from app.api.utils.jwt import calculate_token_ttl, get_token_jti

setup_logging()
logger = logging.getLogger("app")


async def logout_user(token: str) -> bool:
    """
    Logout user by adding their JWT to the Redis denylist.
    The token will be invalid for all subsequent requests.

    Args:
        token: JWT access token to revoke

    Returns:
        True if logout successful
    """
    # Extract JWT ID
    jti = get_token_jti(token)

    if not jti:
        logger.error("Failed to extract jti from token during logout")
        return False

    # Calculate remaining TTL for the token
    ttl = calculate_token_ttl(token)

    # Add to denylist with TTL matching token expiry
    success = await add_token_to_denylist(jti, ttl)

    if success:
        logger.info(f"User logged out successfully, token {jti} denylisted")
    else:
        logger.error(f"Failed to denylist token {jti} during logout")

    return success


async def logout_all_sessions(user_id: str) -> bool:
    """
    Logout user from all devices/sessions.
    Note: This requires tracking all active sessions per user,
    which is not implemented in the current simple JWT approach.

    For full implementation, you would need to:
    1. Store all active JTI values per user in Redis
    2. On logout_all, retrieve all JTIs for user
    3. Add all to denylist

    Args:
        user_id: User UUID

    Returns:
        True if successful
    """
    # TODO: Implement session tracking for logout_all functionality
    logger.warning(f"logout_all_sessions not fully implemented for user {user_id}")
    return False
