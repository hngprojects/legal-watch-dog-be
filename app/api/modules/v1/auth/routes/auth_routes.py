"""
Authentication routes - login, refresh token, and logout endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Body, Response
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.api.db.database import get_db
from app.api.core.redis_client import get_redis
from app.api.core.config import settings
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
    response: Response,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Login endpoint - obtain JWT tokens via HttpOnly cookies.

    **Request Body:**
    - email: User's email address
    - password: User's password

    **Response:**
    - message: Success message
    - user: User information including id, email, name, role, organisation_id

    **Security:**
    - Tokens are set in HttpOnly cookies (not accessible via JavaScript)
    - Access token cookie expires in 60 minutes
    - Refresh token cookie expires in 30 days

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

    # Set access token in HttpOnly cookie
    response.set_cookie(
        key=settings.COOKIE_NAME_ACCESS,
        value=result["access_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.COOKIE_MAX_AGE_ACCESS,
        domain=settings.COOKIE_DOMAIN
    )

    # Set refresh token in HttpOnly cookie
    response.set_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        value=result["refresh_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.COOKIE_MAX_AGE_REFRESH,
        domain=settings.COOKIE_DOMAIN
    )

    # Return response without tokens
    return {
        "message": "Login successful",
        "user": result["user"]
    }


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
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Refresh token endpoint - obtain new JWT tokens via HttpOnly cookies.

    **Request:**
    - Reads refresh_token from HttpOnly cookie

    **Response:**
    - message: Success message

    **Security:**
    - New tokens are set in HttpOnly cookies (not accessible via JavaScript)
    - Old refresh token is automatically invalidated (token rotation)
    - Blacklisted tokens cannot be reused

    **Error Codes:**
    - VALIDATION_ERROR: Missing refresh token cookie
    - INVALID_TOKEN: Token is invalid, expired, or revoked
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get(settings.COOKIE_NAME_REFRESH)
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Refresh token cookie not found"
            }
        )

    result = await AuthService.refresh_access_token(
        db=db,
        redis_client=redis_client,
        refresh_token=refresh_token
    )

    # Handle error responses
    if "error" in result:
        status_code = result.pop("status_code", 400)
        raise HTTPException(status_code=status_code, detail=result)

    # Set new access token in HttpOnly cookie
    response.set_cookie(
        key=settings.COOKIE_NAME_ACCESS,
        value=result["access_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.COOKIE_MAX_AGE_ACCESS,
        domain=settings.COOKIE_DOMAIN
    )

    # Set new refresh token in HttpOnly cookie
    response.set_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        value=result["refresh_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.COOKIE_MAX_AGE_REFRESH,
        domain=settings.COOKIE_DOMAIN
    )

    # Return response without tokens
    return {"message": "Token refreshed successfully"}


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
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Logout endpoint - invalidate current token and clear cookies.

    **Authentication:** Required (access token from HttpOnly cookie)

    **Response:**
    - message: "Logged out successfully"

    **Security:**
    - Reads refresh_token from HttpOnly cookie
    - Blacklists refresh token in Redis
    - Clears both access and refresh token cookies

    **Error Codes:**
    - UNAUTHORIZED: Missing or invalid access token
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get(settings.COOKIE_NAME_REFRESH)
    
    result = await AuthService.logout(
        redis_client=redis_client,
        refresh_token=refresh_token
    )

    # Clear access token cookie
    response.delete_cookie(
        key=settings.COOKIE_NAME_ACCESS,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )

    # Clear refresh token cookie
    response.delete_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )

    return result
