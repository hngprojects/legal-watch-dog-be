import logging
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.redis_service import (
    add_token_to_denylist,
    check_rate_limit,
    get_redis_client,
    reset_rate_limit,
)
from app.api.core.logger import setup_logging
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import calculate_token_ttl, create_access_token, get_token_jti
from app.api.utils.password import verify_password

setup_logging()
logger = logging.getLogger("app")

# Constants for rate limiting
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
RATE_LIMIT_WINDOW_SECONDS = 60


async def check_account_lockout(email: str) -> Optional[int]:
    """
    Check if account is locked due to failed login attempts.

    Args:
        email: User email

    Returns:
        Remaining lockout time in seconds, or None if not locked
    """
    try:
        redis_client = await get_redis_client()
        lockout_key = f"login:lockout:{email}"
        ttl = await redis_client.ttl(lockout_key)

        if ttl > 0:
            return ttl
        return None
    except Exception as e:
        logger.error(f"Failed to check account lockout: {str(e)}")
        return None


async def increment_failed_attempts(email: str) -> int:
    """
    Increment failed login attempts counter.
    After MAX_LOGIN_ATTEMPTS, lock account for LOCKOUT_DURATION_MINUTES.

    Args:
        email: User email

    Returns:
        Current failed attempt count
    """
    try:
        redis_client = await get_redis_client()
        attempts_key = f"login:failed:{email}"

        # Increment counter
        attempts = await redis_client.incr(attempts_key)

        # Set expiry on first attempt (15 minutes)
        if attempts == 1:
            await redis_client.expire(attempts_key, LOCKOUT_DURATION_MINUTES * 60)

        # Lock account if max attempts exceeded
        if attempts >= MAX_LOGIN_ATTEMPTS:
            lockout_key = f"login:lockout:{email}"
            await redis_client.setex(lockout_key, LOCKOUT_DURATION_MINUTES * 60, str(attempts))
            logger.warning(
                f"Account locked for {email}: {attempts} failed attempts. "
                f"Locked for {LOCKOUT_DURATION_MINUTES} minutes."
            )

        return attempts
    except Exception as e:
        logger.error(f"Failed to increment failed attempts: {str(e)}")
        return 0


async def reset_failed_attempts(email: str) -> bool:
    """
    Reset failed login attempts after successful login.

    Args:
        email: User email

    Returns:
        True if successful
    """
    try:
        redis_client = await get_redis_client()
        attempts_key = f"login:failed:{email}"
        lockout_key = f"login:lockout:{email}"

        await redis_client.delete(attempts_key)
        await redis_client.delete(lockout_key)

        logger.info(f"Reset failed attempts for {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to reset attempts: {str(e)}")
        return False


async def store_refresh_token(user_id: str, refresh_token: str, ttl_days: int = 30) -> bool:
    """
    Store refresh token in Redis for token rotation.

    Args:
        user_id: User UUID
        refresh_token: Refresh token string (jti)
        ttl_days: Time-to-live in days

    Returns:
        True if successful
    """
    try:
        redis_client = await get_redis_client()
        key = f"refresh_token:{user_id}:{refresh_token}"
        await redis_client.setex(key, ttl_days * 24 * 3600, "valid")
        logger.info(f"Stored refresh token for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to store refresh token: {str(e)}")
        return False


async def verify_refresh_token(user_id: str, refresh_token: str) -> bool:
    """
    Verify if refresh token is valid and not blacklisted.

    Args:
        user_id: User UUID
        refresh_token: Refresh token string (jti)

    Returns:
        True if valid
    """
    try:
        redis_client = await get_redis_client()
        key = f"refresh_token:{user_id}:{refresh_token}"
        exists = await redis_client.exists(key)
        return bool(exists)
    except Exception as e:
        logger.error(f"Failed to verify refresh token: {str(e)}")
        return False


async def revoke_refresh_token(user_id: str, refresh_token: str) -> bool:
    """
    Revoke a refresh token (token rotation).

    Args:
        user_id: User UUID
        refresh_token: Refresh token string (jti)

    Returns:
        True if successful
    """
    try:
        redis_client = await get_redis_client()
        key = f"refresh_token:{user_id}:{refresh_token}"
        await redis_client.delete(key)
        logger.info(f"Revoked refresh token for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke refresh token: {str(e)}")
        return False


async def authenticate_user(
    db: AsyncSession, email: str, password: str, ip_address: Optional[str] = None
) -> dict:
    """
    Authenticate user with comprehensive security measures:
    - Rate limiting (5 failed attempts)
    - 15-minute account lockout after max failed attempts
    - Secure password verification
    - Token rotation with refresh tokens
    - Role-based access control context

    Args:
        db: Database session
        email: User email
        password: Plain text password
        ip_address: Client IP address for rate limiting

    Returns:
        Dictionary with access_token, refresh_token, and user data

    Raises:
        HTTPException: 429 if account locked or rate limit exceeded
        HTTPException: 401 if credentials invalid
        HTTPException: 403 if account inactive or unverified
    """
    # Check if account is locked
    lockout_ttl = await check_account_lockout(email)
    if lockout_ttl:
        minutes_remaining = lockout_ttl // 60
        logger.warning(f"Login blocked: account {email} is locked")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked due to too many failed login attempts. "
            f"Try again in {minutes_remaining} minutes.",
        )

    # Rate limit by IP if provided (10 attempts per minute)
    if ip_address:
        ip_allowed = await check_rate_limit(
            f"login:ip:{ip_address}",
            max_attempts=10,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )

        if not ip_allowed:
            logger.warning(f"Rate limit exceeded for IP: {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts from this IP. Please try again later.",
            )

    # Fetch user with role for RBAC context
    user = await db.scalar(select(User).where(User.email == email))

    if not user:
        # Increment failed attempts even for non-existent users (prevent enumeration)
        await increment_failed_attempts(email)
        logger.warning(f"Login failed: user not found for email {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(password, user.hashed_password):
        failed_count = await increment_failed_attempts(email)
        remaining = MAX_LOGIN_ATTEMPTS - failed_count

        logger.warning(
            f"Login failed: invalid password for {email}. "
            f"Failed attempts: {failed_count}/{MAX_LOGIN_ATTEMPTS}"
        )

        if failed_count >= MAX_LOGIN_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked due to too many failed attempts. "
                f"Try again in {LOCKOUT_DURATION_MINUTES} minutes.",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email or password. {remaining} attempts remaining.",
        )

    # Check user status
    if not user.is_active:
        logger.warning(f"Login blocked: inactive account {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    if not user.is_verified:
        logger.warning(f"Login blocked: unverified account {email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first.",
        )

    # Fetch user's role for RBAC context
    role = await db.scalar(select(Role).where(Role.id == user.role_id))

    if not role:
        logger.error(f"Login failed: role not found for user {email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role configuration error. Please contact support.",
        )

    # Successful authentication - reset failed attempts
    await reset_failed_attempts(email)
    if ip_address:
        await reset_rate_limit(f"login:ip:{ip_address}")

    # Generate access token
    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        role_id=str(user.role_id),
    )

    # Generate refresh token (longer lived, 30 days)
    # refresh_token_jti = str(uuid.uuid4())
    refresh_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        role_id=str(user.role_id),
        expires_delta=timedelta(days=30),
    )

    refresh_token_jti = get_token_jti(refresh_token)
    # Store refresh token in Redis for rotation
    await store_refresh_token(str(user.id), refresh_token_jti, ttl_days=30)

    logger.info(f"Successful login: {user.email} (org: {user.organization_id}, role: {role.name})")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600 * 24,  # 24 hours in seconds
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "organization_id": str(user.organization_id),
            "role_id": str(user.role_id),
            "role_name": role.name,
            "permissions": role.permissions,
            "is_verified": user.is_verified,
            "is_active": user.is_active,
        },
    }


async def refresh_access_token(db: AsyncSession, user_id: str, old_refresh_token: str) -> dict:
    """
    Token rotation: Generate new access + refresh tokens, revoke old refresh token.
    Implements automatic token rotation for enhanced security.

    Args:
        db: Database session
        user_id: User UUID
        old_refresh_token: Current refresh token to rotate

    Returns:
        Dictionary with new access_token and refresh_token

    Raises:
        HTTPException: 401 if refresh token invalid or revoked
        HTTPException: 404 if user not found
        HTTPException: 403 if user inactive
    """
    # Extract jti from old refresh token
    old_token_jti = get_token_jti(old_refresh_token)
    if not old_token_jti:
        logger.warning(f"Invalid refresh token format for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # Verify refresh token is valid and not blacklisted
    is_valid = await verify_refresh_token(user_id, old_token_jti)
    if not is_valid:
        logger.warning(f"Refresh token validation failed for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has been revoked",
        )

    # Fetch user with role
    user = await db.scalar(select(User).where(User.id == user_id))

    if not user:
        logger.warning(f"Token refresh failed: user {user_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.is_active:
        logger.warning(f"Token refresh blocked: user {user.email} is inactive")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    # Fetch role for context
    role = await db.scalar(select(Role).where(Role.id == user.role_id))
    if not role:
        logger.error(f"Role not found for user {user.email} during token refresh")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User role configuration error",
        )

    # Revoke old refresh token (token rotation)
    await revoke_refresh_token(user_id, old_token_jti)

    # Add old refresh token to denylist
    ttl = calculate_token_ttl(old_refresh_token)
    await add_token_to_denylist(old_token_jti, ttl)

    # Generate new access token
    new_access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        role_id=str(user.role_id),
    )

    # Generate new refresh token
    new_refresh_token_jti = str(uuid.uuid4())
    new_refresh_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        role_id=str(user.role_id),
        expires_delta=timedelta(days=30),
    )

    # Store new refresh token
    await store_refresh_token(str(user.id), new_refresh_token_jti, ttl_days=30)

    logger.info(f"Token rotated for user: {user.email} (old jti: {old_token_jti[:8]}...)")

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": 3600 * 24,
    }


class LoginService:
    """
    Login service implementing secure authentication with:
    - Rate limiting
    - Account lockout
    - Token rotation
    - RBAC support
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str, ip_address: Optional[str] = None) -> dict:
        """
        Authenticate user and return tokens.

        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP for rate limiting

        Returns:
            Dictionary with tokens and user data
        """
        return await authenticate_user(self.db, email, password, ip_address)

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Rotate tokens using refresh token.

        Args:
            refresh_token: Current refresh token

        Returns:
            Dictionary with new tokens
        """
        from app.api.utils.jwt import decode_token

        # Decode to get user_id
        try:
            payload = decode_token(refresh_token)
            user_id = payload.get("sub")

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized",
                )

            return await refresh_access_token(self.db, user_id, refresh_token)
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

    async def logout(self, user_id: str) -> dict:
        """
        Logout user and clear their tokens.

        Args:
            user_id: User UUID

        Returns:
            Logout confirmation
        """
        try:
            # Clear failed attempts
            user = await self.db.scalar(select(User).where(User.id == user_id))
            if user:
                await reset_failed_attempts(user.email)

            logger.info(f"User {user_id} logged out successfully")

            return {"message": "Logged out successfully", "success": True}
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed",
            )
