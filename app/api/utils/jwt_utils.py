"""
JWT token utilities for authentication.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import uuid
import jwt
from app.api.core.config import settings


class JWTManager:
    """
    JWT token creation and validation utilities.
    """

    @staticmethod
    def create_access_token(
        user_id: uuid.UUID,
        organisation_id: uuid.UUID,
        role: str,
        email: str
    ) -> str:
        """
        Create JWT access token.

        Args:
            user_id: User's unique ID
            organisation_id: Organisation's unique ID
            role: User's role name
            email: User's email address

        Returns:
            str: Encoded JWT access token
        """
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.now(timezone.utc) + expires_delta

        payload = {
            "sub": str(user_id),
            "organisation_id": str(organisation_id),
            "role": role,
            "email": email,
            "exp": expire,
            "type": "access"
        }

        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
        """
        Create JWT refresh token with unique JTI.

        Args:
            user_id: User's unique ID

        Returns:
            tuple: (encoded token, jti)
        """
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.now(timezone.utc) + expires_delta
        jti = str(uuid.uuid4())

        payload = {
            "sub": str(user_id),
            "jti": jti,
            "exp": expire,
            "type": "refresh"
        }

        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        return token, jti

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token.

        Args:
            token: JWT token string

        Returns:
            dict: Decoded token payload

        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify access token and return payload.

        Args:
            token: JWT access token string

        Returns:
            dict: Token payload if valid, None otherwise
        """
        try:
            payload = JWTManager.decode_token(token)
            if payload.get("type") != "access":
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    @staticmethod
    def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify refresh token and return payload.

        Args:
            token: JWT refresh token string

        Returns:
            dict: Token payload if valid, None otherwise
        """
        try:
            payload = JWTManager.decode_token(token)
            if payload.get("type") != "refresh":
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
