from app.api.utils.jwt import get_token_jti, calculate_token_ttl
from app.api.core.dependencies.redis_service import add_token_to_denylist
from app.api.core.logger import setup_logging
import logging

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