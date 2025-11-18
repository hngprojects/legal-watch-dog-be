"""
Authentication dependencies for FastAPI endpoints.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api.db.database import get_db
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt_utils import JWTManager
from app.api.core.config import settings


# OAuth2 scheme for token authentication (kept for OpenAPI docs compatibility)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from JWT token in HttpOnly cookie.

    Args:
        request: FastAPI request object (to access cookies)
        db: Database session

    Returns:
        User: Current authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Get token from HttpOnly cookie
    token = request.cookies.get(settings.COOKIE_NAME_ACCESS)
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token not found in cookies. Please login.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify and decode token
    payload = JWTManager.verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    # Fetch user from database
    statement = select(User).where(User.id == user_id)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact your administrator."
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user.

    Args:
        current_user: User from get_current_user dependency

    Returns:
        User: Current active user

    Raises:
        HTTPException: 403 if user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact your administrator."
        )
    return current_user


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        str: Client IP address
    """
    # Check for X-Forwarded-For header (if behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client
    return request.client.host if request.client else "unknown"
