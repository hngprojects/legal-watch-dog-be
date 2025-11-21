import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas.login import LoginRequest, RefreshTokenRequest
from app.api.modules.v1.auth.service.login_service import LoginService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import fail_response, success_response

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description=(
        "Authenticate user and return access/refresh tokens with rate limiting protection"
    ),
)
async def login(request: Request, login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login endpoint with security features:
    - Rate limiting (5 failed attempts, 15-minute lockout)
    - Secure password verification
    - Token rotation
    - Refresh token blacklisting
    """
    email = None
    is_oauth = False
    try:
        # Determine if request is JSON or form
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            data = await request.json()
            email = data.get("email")
            password = data.get("password")
            is_oauth = False
        else:
            form = await request.form()
            email = form.get("username")
            password = form.get("password")
            is_oauth = True

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")

        login_service = LoginService(db)

        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else "unknown"

        result = await login_service.login(
            email=login_data.email, password=login_data.password, ip_address=client_ip
        )

        if is_oauth:
            return {"access_token": result["access_token"], "token_type": "bearer"}
        else:
            token_data = {
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "token_type": result["token_type"],
                "expires_in": result["expires_in"],
            }

            return success_response(
                status_code=status.HTTP_200_OK,
                message="Login successful",
                data=token_data,
            )
    except HTTPException as e:
        if is_oauth:
            raise
        else:
            logger.warning("Login failed for email=%s: %s", email or "unknown", e.detail)
            return fail_response(
                status_code=e.status_code,
                message=e.detail,
            )
    except Exception:
        logger.exception("Unexpected error during login for email=%s", login_data.email)
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
        )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Refresh access token using a valid refresh token with token rotation",
)
async def refresh_token(refresh_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh token endpoint:
    - Validates refresh token
    - Blacklists old refresh token
    - Issues new access and refresh tokens
    """
    try:
        login_service = LoginService(db)

        result = await login_service.refresh_access_token(refresh_token=refresh_data.refresh_token)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Token refreshed successfully",
            data=result,
        )
    except HTTPException as e:
        logger.warning("Token refresh failed: %s", e.detail)
        return fail_response(
            status_code=e.status_code,
            message=e.detail,
        )
    except Exception:
        logger.exception("Unexpected error during token refresh")
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Logout user and blacklist their tokens",
)
async def logout(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Logout endpoint:
    - Blacklists access token
    - Blacklists refresh token
    - Clears rate limiting data
    """
    try:
        login_service = LoginService(db)

        result = await login_service.logout(user_id=str(current_user.id))

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Logged out successfully",
            data=result,
        )
    except HTTPException as e:
        logger.warning("Logout failed for user_id=%s: %s", str(current_user.id), e.detail)
        return fail_response(
            status_code=e.status_code,
            message=e.detail,
        )
    except Exception:
        logger.exception("Unexpected error during logout for user_id=%s", str(current_user.id))
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
        )
