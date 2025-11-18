from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
import uuid
from app.api.core.config import settings
from app.api.core.logger import setup_logging
import logging

setup_logging()
logger = logging.getLogger("app")


def create_access_token(
    user_id: str,
    organization_id: str,
    role_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token with user and organization context.

    Args:
        user_id: UUID of the user
        organization_id: UUID of the organization
        role_id: UUID of the user's role
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)

    # Generate unique JWT ID for revocation tracking
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "org_id": str(organization_id),
        "role_id": str(role_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": jti,  # JWT ID for revocation
    }

    encoded_jwt = jwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    logger.info(f"Created JWT for user {user_id}, org {organization_id}, jti: {jti}")
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Attempted to decode expired JWT token")
        raise
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {str(e)}")
        raise


def get_token_jti(token: str) -> Optional[str]:
    """
    Extract the JWT ID (jti) from a token without full validation.
    Used for adding tokens to the denylist during logout.

    Args:
        token: JWT token string

    Returns:
        JWT ID (jti) or None if extraction fails
    """
    try:
        # Decode without verification to get jti even for expired tokens
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        return unverified_payload.get("jti")
    except Exception as e:
        logger.error(f"Failed to extract jti from token: {str(e)}")
        return None


def calculate_token_ttl(token: str) -> int:
    """
    Calculate remaining time-to-live for a token in seconds.
    Used to set Redis TTL when denylisting tokens.

    Args:
        token: JWT token string

    Returns:
        TTL in seconds, or default if calculation fails
    """
    try:
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        exp = unverified_payload.get("exp")
        if exp:
            ttl = exp - datetime.now(timezone.utc).timestamp()
            return max(int(ttl), 0)
        return settings.JWT_EXPIRY_HOURS * 3600
    except Exception:
        return settings.JWT_EXPIRY_HOURS * 3600
