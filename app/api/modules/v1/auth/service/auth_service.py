# app/api/modules/v1/auth/auth_service.py

import logging
import secrets
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

import anyio
import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from jose import jwt
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.auth.models.login_models import User, RefreshToken
from app.api.core.config import settings

logger = logging.getLogger(__name__)

# Argon2id hasher - current best practice (2025)
ph = PasswordHasher(
    time_cost=3,  
    memory_cost=65536, 
    parallelism=4, 
    hash_len=32,
    salt_len=16,
)

# Keep this if you had the pre-hashed bcrypt version before
LEGACY_HMAC_SALT = b"legal_watch_dog_fixed_salt"


class AuthService:
    """Handles authentication, password hashing, and token creation."""

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Hash a password using Argon2id.

        """
        return ph.hash(password)

    @staticmethod
    async def get_password_hash_async(password: str) -> str:
        """
        Async version of get_password_hash - safe to call from async contexts.
        """

        def _hash_sync():
            return ph.hash(password)

        return await anyio.to_thread.run_sync(_hash_sync)

    @staticmethod
    async def verify_password(plain_password: str, stored_hash: str) -> bool:
        """Verify a password against a stored hash."""
        try:
            # 1. New Argon2 hashes
            if stored_hash.startswith("$argon2"):

                def _argon2_verify():
                    ph.verify(stored_hash, plain_password)

                await anyio.to_thread.run_sync(_argon2_verify)
                return True

            # 2. Your previous base64 bcrypt format (with HMAC prehash)
            elif len(stored_hash) <= 120 and "$" not in stored_hash[:10]:

                def _legacy_bcrypt_verify():
                    prehashed = hmac.new(
                        LEGACY_HMAC_SALT, plain_password.encode("utf-8"), hashlib.sha256
                    ).digest()
                    stored_bytes = base64.b64decode(stored_hash)
                    return bcrypt.checkpw(prehashed, stored_bytes)

                return await anyio.to_thread.run_sync(_legacy_bcrypt_verify)

            # 3. Old passlib bcrypt format
            elif stored_hash.startswith(("$2a$", "$2b$", "$2y$")):

                def _old_bcrypt_verify():
                    return bcrypt.checkpw(plain_password.encode(), stored_hash.encode())

                return await anyio.to_thread.run_sync(_old_bcrypt_verify)

            else:
                logger.warning(f"Unknown password hash format: {stored_hash[:20]}...")
                return False

        except (
            VerifyMismatchError,
            InvalidHashError,
            ValueError,
            base64.binascii.Error,
        ):
            return False
        except Exception as e:
            logger.error(f"Unexpected error during password verification: {e}")
            return False

    @staticmethod
    async def authenticate_user(
        db: AsyncSession, email: str, password: str
    ) -> Optional[User]:
        """Authenticate a user by email and password."""
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"Login failed - user not found: {email}")
            return None

        if user.status != "active":
            logger.warning(f"Login failed - user inactive: {email}")
            return None

        if not await AuthService.verify_password(password, user.hashed_password):
            logger.warning(f"Login failed - invalid password: {email}")
            return None

        # Auto-upgrade old hashes to Argon2id
        if not user.hashed_password.startswith("$argon2"):
            logger.info(f"Upgrading password hash to Argon2id for user: {email}")
            user.hashed_password = await AuthService.get_password_hash_async(password)
            await db.commit()

        logger.info(f"User authenticated successfully: {email}")
        return user

    @staticmethod
    def create_access_token(
        data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire, "token_type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_refresh_token() -> str:
        """Generate a secure random refresh token."""
        return secrets.token_urlsafe(64)

    @staticmethod
    async def create_tokens(
        db: AsyncSession, user: User, ip_address: Optional[str] = None
    ) -> Tuple[str, str, RefreshToken]:
        """Create access token + refresh token + store refresh token in DB."""
        access_token = AuthService.create_access_token(
            {
                "sub": str(user.user_id),
                "email": user.email,
                "org_id": str(user.org_id),
                "role_id": str(user.role_id),
            }
        )

        refresh_token_value = AuthService.create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        refresh_token = RefreshToken(
            token=refresh_token_value,
            user_id=user.user_id,
            expires_at=expires_at,
            created_by_ip=ip_address,
        )

        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)

        return access_token, refresh_token_value, refresh_token
