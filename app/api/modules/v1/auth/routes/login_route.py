import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.login_route_docs import (
    login_custom_errors,
    login_custom_success,
    login_responses,
    logout_custom_errors,
    logout_custom_success,
    logout_responses,
    refresh_custom_errors,
    refresh_custom_success,
    refresh_token_responses,
)
from app.api.modules.v1.auth.schemas.login import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.api.modules.v1.auth.service.login_service import LoginService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.cookie_helper import clear_auth_cookies
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses=login_responses,  # type: ignore
)
async def login(request: Request, login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and issue access and refresh tokens.

    This endpoint supports:
    - Secure password verification
    - Token rotation for refresh tokens
    - OAuth2-style form login or JSON login payload

    Args:
        request (Request): The incoming HTTP request.
        login_data (LoginRequest): Pydantic schema containing email and password.
        db (AsyncSession, optional): Database session dependency.

    Returns:
        JSON response with success or error payload:
        - On success: access_token, refresh_token, token_type, expires_in
        - On failure: appropriate error message
    """
    try:
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            data = await request.json()
            email = data.get("email")
            password = data.get("password")
        else:
            form = await request.form()
            email = form.get("username")
            password = form.get("password")

        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")

        login_service = LoginService(db)
        client_ip = request.client.host if request.client else "unknown"

        result = await login_service.login(email=email, password=password, ip_address=client_ip)

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
        logger.warning("Login failed for email=%s: %s", login_data.email, e.detail)
        return error_response(status_code=e.status_code, message=e.detail)
    except Exception:
        logger.exception("Unexpected error during login for email=%s", login_data.email)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Internal server error",
        )


login._custom_errors = login_custom_errors  # type: ignore
login._custom_success = login_custom_success  # type: ignore


@router.post(
    "/token/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    responses=refresh_token_responses,  # type: ignore
)
async def refresh_token(refresh_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh access and refresh tokens using a valid refresh token.

    This endpoint:
    - Validates the provided refresh token.
    - Blacklists the old refresh token.
    - Issues new access and refresh tokens.

    Args:
        refresh_data (RefreshTokenRequest): Pydantic schema containing the refresh token.
        db (AsyncSession, optional): Database session dependency.

    Returns:
        JSON response with the new tokens or error details.
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
        return error_response(status_code=e.status_code, message=e.detail)
    except Exception:
        logger.exception("Unexpected error during token refresh")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Internal server error",
        )


refresh_token._custom_errors = refresh_custom_errors  # type: ignore
refresh_token._custom_success = refresh_custom_success  # type: ignore


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses=logout_responses,
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout the current user by invalidating their tokens.

    This endpoint:

    - Blacklists the user's current access token
    - Blacklists the user's current refresh token

    Args:
        request: HTTP request to extract token from header
        current_user: Currently authenticated user from dependency.
        db: Database session dependency.


    Returns:
        JSON response confirming logout or error details.
    """
    try:
        auth_header = request.headers.get("authorization")
        token = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")

        login_service = LoginService(db)

        await login_service.logout(user_id=str(current_user.id), token=token)

        response_data = {
            "status": "SUCCESS",
            "status_code": status.HTTP_200_OK,
            "message": "Logged out successfully",
            "data": {},
        }

        # Create JSONResponse to enable cookie manipulation
        response = JSONResponse(
            content=response_data,
            status_code=status.HTTP_200_OK,
        )

        # Clear authentication cookies
        clear_auth_cookies(response=response, request=request)

        logger.info("User %s logged out successfully", str(current_user.id))

        return response
    except HTTPException as e:
        logger.warning("Logout failed for user_id=%s: %s", str(current_user.id), e.detail)
        return error_response(
            status_code=e.status_code,
            message=e.detail,
        )
    except Exception:
        logger.exception("Unexpected error during logout for user_id=%s", str(current_user.id))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Internal server error",
        )


logout._custom_errors = logout_custom_errors
logout._custom_success = logout_custom_success
