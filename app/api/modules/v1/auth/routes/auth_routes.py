"""
Authentication routes - login, refresh token, and logout endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.api.db.database import get_db
from app.api.core.redis_client import get_redis
from app.api.core.dependencies.auth_dependencies import get_current_user, get_client_ip
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.auth.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutResponse,
    ErrorResponse
)
from app.api.modules.v1.auth.service.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Validation error - email and password are required"
        },
        401: {
            "model": ErrorResponse,
            "description": "Invalid credentials - incorrect email or password"
        },
        403: {
            "model": ErrorResponse,
            "description": "Account inactive - account has been deactivated"
        },
        429: {
            "model": ErrorResponse,
            "description": "Rate limit exceeded - too many failed login attempts"
        }
    },
    summary="User Login",
    description="Authenticate user and obtain JWT access and refresh tokens. "
                "Rate limited to 5 failed attempts per email with 15-minute lockout."
)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Login endpoint - obtain JWT tokens.

    **Request Body:**
    - email: User's email address
    - password: User's password

    **Response:**
    - access_token: JWT access token (60 minutes expiry)
    - refresh_token: JWT refresh token (30 days expiry)
    - token_type: "bearer"
    - user: User information including id, email, name, role, organisation_id

    **Error Codes:**
    - VALIDATION_ERROR: Missing or invalid input
    - INVALID_CREDENTIALS: Wrong email or password
    - ACCOUNT_INACTIVE: Account has been deactivated
    - RATE_LIMIT_EXCEEDED: Too many failed attempts
    """
    client_ip = get_client_ip(request)

    result = await AuthService.login(
        db=db,
        redis_client=redis_client,
        email=login_data.email,
        password=login_data.password,
        client_ip=client_ip
    )

    # Handle error responses
    if "error" in result:
        status_code = result.pop("status_code", 400)
        raise HTTPException(status_code=status_code, detail=result)

    return result


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Validation error - refresh token is required"
        },
        401: {
            "model": ErrorResponse,
            "description": "Invalid token - refresh token is invalid or expired"
        }
    },
    summary="Refresh Access Token",
    description="Exchange a valid refresh token for new access and refresh tokens. "
                "Implements token rotation - old refresh token is invalidated."
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Refresh token endpoint - obtain new JWT tokens.

    **Request Body:**
    - refresh_token: Valid refresh token

    **Response:**
    - access_token: New JWT access token (60 minutes expiry)
    - refresh_token: New JWT refresh token (30 days expiry)

    **Notes:**
    - Old refresh token is automatically invalidated (token rotation)
    - Blacklisted tokens cannot be reused

    **Error Codes:**
    - VALIDATION_ERROR: Missing refresh token
    - INVALID_TOKEN: Token is invalid, expired, or revoked
    """
    result = await AuthService.refresh_access_token(
        db=db,
        redis_client=redis_client,
        refresh_token=refresh_data.refresh_token
    )

    # Handle error responses
    if "error" in result:
        status_code = result.pop("status_code", 400)
        raise HTTPException(status_code=status_code, detail=result)

    return result


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized - authentication required"
        }
    },
    summary="User Logout",
    description="Invalidate current refresh token and logout user. "
                "Requires authentication via access token."
)
async def logout(
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
    refresh_token: Optional[str] = Body(None, embed=True)
):
    """
    Logout endpoint - invalidate current token.

    **Authentication:** Required (Bearer token in Authorization header)

    **Request Body (optional):**
    - refresh_token: Refresh token to invalidate

    **Response:**
    - message: "Logged out successfully"

    **Notes:**
    - Access token is validated via Authorization header
    - If refresh_token is provided in body, it will be blacklisted
    - Blacklisted tokens cannot be used to refresh access tokens

    **Error Codes:**
    - UNAUTHORIZED: Missing or invalid access token
    """
    result = await AuthService.logout(
        redis_client=redis_client,
        refresh_token=refresh_token
    )

    return result
