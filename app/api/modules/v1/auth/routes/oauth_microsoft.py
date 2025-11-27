import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.registeration_redis import get_redis
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.oauth_microsoft import (
    microsoft_callback_custom_errors,
    microsoft_callback_custom_success,
    microsoft_callback_responses,
    microsoft_login_custom_errors,
    microsoft_login_custom_success,
    microsoft_login_responses,
)
from app.api.modules.v1.auth.schemas.oauth_microsoft import (
    MicrosoftAuthResponse,
)
from app.api.modules.v1.auth.service.oauth_microsoft import MicrosoftOAuthService
from app.api.utils.response_payloads import error_response

router = APIRouter(prefix="/auth/microsoft", tags=["Social Auth"])

logger = logging.getLogger("app")


@router.get(
    "/login",
    response_model=MicrosoftAuthResponse,
    status_code=status.HTTP_200_OK,
    responses=microsoft_login_responses,  # type: ignore
)
async def microsoft_login(
    redirect_uri: Optional[str] = Query(None, description="Custom redirect URI"),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Initiate Microsoft OAuth login flow.

    Returns authorization URL that the client should redirect to.
    The user will authenticate with Microsoft and be redirected back
    to the callback endpoint with an authorization code.

    Args:
        redirect_uri: Optional custom redirect URI (must be registered in Azure AD)
        db: Database session dependency
        redis_client: Redis client dependency

    Returns:
        Authorization URL and state parameter for CSRF protection
    """
    try:
        service = MicrosoftOAuthService(db, redis_client)
        authorization_url, state = await service.generate_authorization_url(redirect_uri)

        return {
            "authorization_url": authorization_url,
            "state": state,
        }

    except Exception as e:
        logger.error("Failed to generate Microsoft OAuth URL: %s", str(e), exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to initiate Microsoft login",
        )


microsoft_login._custom_errors = microsoft_login_custom_errors  # type: ignore
microsoft_login._custom_success = microsoft_login_custom_success  # type: ignore


@router.get(
    "/callback",
    status_code=status.HTTP_302_FOUND,
    responses=microsoft_callback_responses,  # type: ignore
)
async def microsoft_callback(
    code: str = Query(..., description="Authorization code from Microsoft"),
    state: str = Query(..., description="State parameter for validation"),
    error: Optional[str] = Query(None, description="Error from Microsoft"),
    error_description: Optional[str] = Query(None, description="Error description"),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Handle Microsoft OAuth callback and redirect to frontend with cookies set.
    Uses frontend URLs from environment variables.
    """
    frontend_redirect_new_user_url = settings.MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL
    frontend_redirect_existing_user_url = settings.MICROSOFT_OAUTH_REDIRECT_EXISTING_USER_URL

    if error:
        logger.warning(
            "Microsoft OAuth error: %s - %s", error, error_description or "No description"
        )
        frontend_error_url = f"{frontend_redirect_new_user_url}?error={error}"
        return RedirectResponse(url=frontend_error_url)

    try:
        service = MicrosoftOAuthService(db, redis_client)
        result = await service.complete_oauth_flow(code, state)

        if result["is_new_user"]:
            redirect_url = f"{frontend_redirect_new_user_url}"
        else:
            redirect_url = f"{frontend_redirect_existing_user_url}"

        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        if settings.ENVIRONMENT == "production":
            samesite = "none"
            secure = True
        else:
            samesite = "lax"
            secure = False

        response.set_cookie(
            key="lwd_access_token",
            value=result["access_token"],
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=86400,
            path="/",
        )

        response.set_cookie(
            key="lwd_refresh_token",
            value=result["refresh_token"],
            httponly=True,
            secure=secure,
            samesite=samesite,
            max_age=2592000,
            path="/",
        )

        logger.info(
            "Successfully authenticated user %s via Microsoft OAuth, redirecting to %s",
            result["email"],
            redirect_url,
        )

        return response

    except ValueError as e:
        logger.warning("Microsoft OAuth validation error: %s", str(e))
        return RedirectResponse(
            url=f"{frontend_redirect_new_user_url}/login?error=validation_failed"
        )

    except Exception as e:
        logger.error("Failed to complete Microsoft OAuth flow: %s", str(e), exc_info=True)
        return RedirectResponse(
            url=f"{frontend_redirect_new_user_url}/login?error=authentication_failed"
        )


microsoft_callback._custom_errors = microsoft_callback_custom_errors  # type: ignore
microsoft_callback._custom_success = microsoft_callback_custom_success  # type: ignore
