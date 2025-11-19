from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas.login import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.api.modules.v1.auth.service.login_service import LoginService
from app.api.core.dependencies.auth import get_current_user
from app.api.modules.v1.users.models.users_model import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description=(
        "Authenticate user and return access/refresh tokens "
        "with rate limiting protection"
    ),
)
async def login(
    request: Request, login_data: LoginRequest, db: AsyncSession = Depends(get_db)
):
    """
    Login endpoint with security features:
    - Rate limiting (5 failed attempts, 15-minute lockout)
    - Secure password verification
    - Token rotation
    - Refresh token blacklisting
    """
    login_service = LoginService(db)

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    result = await login_service.login(
        email=login_data.email, password=login_data.password, ip_address=client_ip
    )

    return result


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Refresh access token using a valid refresh token with token rotation",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
):
    """
    Refresh token endpoint:
    - Validates refresh token
    - Blacklists old refresh token
    - Issues new access and refresh tokens
    """
    login_service = LoginService(db)

    result = await login_service.refresh_access_token(
        refresh_token=refresh_data.refresh_token
    )

    return result



