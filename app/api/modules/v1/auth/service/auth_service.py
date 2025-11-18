"""
Authentication service - business logic for login, refresh, and logout.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import redis.asyncio as redis
import uuid

from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt_utils import JWTManager
from app.api.utils.password_utils import PasswordManager
from app.api.modules.v1.auth.service.rate_limiter import RateLimiter
from app.api.core.config import settings


class AuthService:
    """
    Authentication service for user login, token refresh, and logout.
    """

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate user by email and password.

        Args:
            db: Database session
            email: User's email address
            password: Plain text password

        Returns:
            User: Authenticated user if credentials are valid, None otherwise
        """
        statement = (
            select(User)
            .where(User.email == email)
            .options(
                selectinload(User.role),
                selectinload(User.organization)
            )
        )
        result = await db.execute(statement)
        user = result.scalar_one_or_none()

        if user is None:
            return None

        if not PasswordManager.verify_password(password, user.hashed_password):
            return None

        return user

    @staticmethod
    async def login(
        db: AsyncSession,
        redis_client: redis.Redis,
        email: str,
        password: str,
        client_ip: str
    ) -> dict:
        """
        Handle user login with rate limiting.

        Args:
            db: Database session
            redis_client: Redis client for rate limiting
            email: User's email address
            password: Plain text password
            client_ip: Client IP address for rate limiting

        Returns:
            dict: Login response with tokens and user info

        Raises:
            dict: Error response with appropriate error code and message
        """
        # Check rate limit
        is_allowed, retry_after = await RateLimiter.check_rate_limit(redis_client, email)
        if not is_allowed:
            return {
                "error": "RATE_LIMIT_EXCEEDED",
                "message": "Too many failed login attempts. Please try again later.",
                "retry_after": retry_after,
                "status_code": 429
            }

        # Authenticate user
        user = await AuthService.authenticate_user(db, email, password)

        if user is None:
            # Increment failed attempts
            await RateLimiter.increment_failed_attempts(redis_client, email)
            return {
                "error": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "status_code": 401
            }

        # Check if account is active
        if not user.is_active:
            return {
                "error": "ACCOUNT_INACTIVE",
                "message": "Account has been deactivated. Please contact your administrator.",
                "status_code": 403
            }

        # Reset failed attempts on successful login
        await RateLimiter.reset_failed_attempts(redis_client, email)

        # Create tokens
        access_token = JWTManager.create_access_token(
            user_id=user.id,
            organisation_id=user.organization_id,
            role=user.role.name,
            email=user.email
        )

        refresh_token, jti = JWTManager.create_refresh_token(user_id=user.id)

        # Return success response
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role.name,
                "organisation_id": str(user.organization_id)
            },
            "status_code": 200
        }

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        redis_client: redis.Redis,
        refresh_token: str
    ) -> dict:
        """
        Refresh access token using refresh token with rotation.

        Args:
            db: Database session
            redis_client: Redis client for token blacklist
            refresh_token: Current refresh token

        Returns:
            dict: Response with new tokens or error

        Raises:
            dict: Error response with appropriate error code and message
        """
        # Verify refresh token
        payload = JWTManager.verify_refresh_token(refresh_token)
        if payload is None:
            return {
                "error": "INVALID_TOKEN",
                "message": "Refresh token is invalid or has expired",
                "status_code": 401
            }

        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti and await RateLimiter.is_token_blacklisted(redis_client, jti):
            return {
                "error": "INVALID_TOKEN",
                "message": "Refresh token has been revoked",
                "status_code": 401
            }

        # Get user
        user_id_str = payload.get("sub")
        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            return {
                "error": "INVALID_TOKEN",
                "message": "Invalid token format",
                "status_code": 401
            }

        statement = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.role),
                selectinload(User.organization)
            )
        )
        result = await db.execute(statement)
        user = result.scalar_one_or_none()

        if user is None:
            return {
                "error": "INVALID_TOKEN",
                "message": "User not found",
                "status_code": 401
            }

        # Check if user is active
        if not user.is_active:
            return {
                "error": "ACCOUNT_INACTIVE",
                "message": "Account has been deactivated",
                "status_code": 403
            }

        # Blacklist old refresh token
        if jti:
            # Calculate remaining TTL
            exp = payload.get("exp")
            if exp:
                ttl = exp - int(datetime.now(timezone.utc).timestamp())
                if ttl > 0:
                    await RateLimiter.blacklist_token(redis_client, jti, ttl)

        # Create new tokens (token rotation)
        new_access_token = JWTManager.create_access_token(
            user_id=user.id,
            organisation_id=user.organization_id,
            role=user.role.name,
            email=user.email
        )

        new_refresh_token, new_jti = JWTManager.create_refresh_token(user_id=user.id)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "status_code": 200
        }

    @staticmethod
    async def logout(
        redis_client: redis.Redis,
        refresh_token: Optional[str] = None
    ) -> dict:
        """
        Logout user by blacklisting refresh token.

        Args:
            redis_client: Redis client for token blacklist
            refresh_token: Refresh token to blacklist (optional)

        Returns:
            dict: Logout response
        """
        if refresh_token:
            # Verify and blacklist refresh token
            payload = JWTManager.verify_refresh_token(refresh_token)
            if payload:
                jti = payload.get("jti")
                exp = payload.get("exp")
                if jti and exp:
                    ttl = exp - int(datetime.now(timezone.utc).timestamp())
                    if ttl > 0:
                        await RateLimiter.blacklist_token(redis_client, jti, ttl)

        return {
            "message": "Logged out successfully",
            "status_code": 200
        }
