import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.oauth import oauth
from app.api.db.database import get_db
from app.api.modules.v1.auth.service.google_oauth_service import GoogleOAuthService
from app.api.utils.cookie_helper import set_auth_cookies
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth/google", tags=["Social Auth"])


@router.get("/login")
async def google_login(request: Request):
    """
    Initiate Google OAuth2 login flow.

    Generates CSRF state token and redirects to Google's OAuth consent screen.
    The state token prevents CSRF attacks by ensuring the callback comes from
    the same user who initiated the request.

    Args:
        request: HTTP request object

    Returns:
        RedirectResponse to Google OAuth endpoint

    Raises:
        HTTPException: If state generation fails
    """
    try:
        service = GoogleOAuthService(db=None, request=request)
        state = await service.generate_oauth_state()

        redirect_uri = settings.GOOGLE_REDIRECT_URI
        logger.info(f"Initiating Google OAuth login with state from IP {service.client_ip}")

        return await oauth.google.authorize_redirect(request, redirect_uri, state=state)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate Google login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login initiation failed",
        )


@router.get("/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth2 callback.

    Processes OAuth callback with:
    - CSRF state validation
    - ID token verification
    - User creation/retrieval
    - JWT token generation
    - Profile data storage
    - Bearer token pattern (Authorization header, not cookies for access token)

    Args:
        request: HTTP request
        code: Authorization code from Google
        state: CSRF state parameter
        db: Database session

    Returns:
        RedirectResponse with tokens in URL fragment or error redirect

    Raises:
        HTTPException: On authentication errors
    """
    try:
        service = GoogleOAuthService(db=db, request=request)

        await service.validate_oauth_state(state)

        token = await oauth.google.authorize_access_token(request)

        result = await service.complete_oauth_flow(token)

        cookie_settings = GoogleOAuthService.get_cookie_settings(request)

        frontend_url = cookie_settings["frontend_url"]
        access_token = result["access_token"]
        refresh_token = result["refresh_token"]
        is_new_user = result["is_new_user"]

        logger.info(
            f"Successful Google OAuth for user (new={is_new_user}) from IP {service.client_ip}"
        )

        response = RedirectResponse(
            url=f"{frontend_url}/auth/google/callback?is_new_user={str(is_new_user).lower()}#access_token={access_token}&refresh_token={refresh_token}&token_type=bearer",
            status_code=302,
        )


        #  response.set_cookie(
        #     key="refresh_token",
        #     value=refresh_token,
        #     httponly=True,
        #     secure=cookie_settings["secure"],
        #     max_age=30 * 24 * 60 * 60,
        #     domain=cookie_settings["domain"],
        #     path="/",
        #     samesite=cookie_settings["samesite"],
        #  )
        # Set authentication cookies using centralized utility
        set_auth_cookies(
            response=response,
            request=request,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        logger.debug("Set authentication cookies for Google OAuth user")

        return response

    except HTTPException as he:
        raise he

    except Exception as e:
        logger.error(f"Google OAuth callback error: {str(e)}", exc_info=True)

        try:
            cookie_settings = GoogleOAuthService.get_cookie_settings(request)
            frontend_url = cookie_settings["frontend_url"]
        except Exception as url_error:
            logger.error(f"Failed to get cookie settings: {str(url_error)}")
            frontend_url = settings.APP_URL

        error_code = str(uuid.uuid4())
        logger.error(f"OAuth error {error_code}: {str(e)}")

        return RedirectResponse(
            url=f"{frontend_url}/login?error=auth_failed&code={error_code}",
            status_code=302,
        )


@router.get("/profile")
async def get_oauth_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch current Google OAuth profile information.

    This endpoint is called by the frontend to retrieve the current user's
    profile data including picture and provider metadata.

    Args:
        request: HTTP request
        db: Database session

    Returns:
        Success response with user profile and OAuth metadata
    """
    try:
        from app.api.core.dependencies.auth import get_current_user

        current_user = await get_current_user(credentials=None, db=db)

        profile_data = {
            "id": str(current_user.id),
            "email": current_user.email,
            "name": current_user.name,
            "profile_picture_url": current_user.profile_picture_url,
            "auth_provider": current_user.auth_provider,
            "provider_user_id": current_user.provider_user_id,
            "provider_profile_data": current_user.provider_profile_data,
            "is_verified": current_user.is_verified,
            "created_at": current_user.created_at.isoformat(),
        }

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Profile retrieved successfully",
            data=profile_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch OAuth profile: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve profile",
            error="PROFILE_FETCH_ERROR",
        )
