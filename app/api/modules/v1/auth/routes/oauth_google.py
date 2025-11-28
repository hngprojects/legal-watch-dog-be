import logging
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.redis_service import get_redis_client
from app.api.core.oauth import oauth
from app.api.db.database import get_db
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.jwt import create_access_token, get_token_jti

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth/google", tags=["Social Auth"])


def get_cookie_settings(request: Request):
    """
    Dynamically determine cookie settings based on the request origin.
    Uses existing config variables (APP_URL, DEV_URL) to determine environment.
    """
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    # Use origin if available, otherwise parse from referer
    source_url = origin if origin else referer

    logger.info(f"Determining cookie settings for origin: {origin}, referer: {referer}")

    # Check if it's local development
    is_local = "localhost" in source_url or "127.0.0.1" in source_url

    if is_local:
        # Local development environment
        return {
            "domain": None,  # Don't set domain for localhost
            "secure": False,  # HTTP for local dev
            "samesite": "lax",  # Lax is fine for same-origin localhost
            "frontend_url": settings.DEV_URL,
        }
    else:
        # Production/Staging environment (uses APP_URL from config)
        # Extract domain from APP_URL for cookie sharing across subdomains
        parsed = urlparse(settings.APP_URL)

        # Create wildcard domain (e.g., .minamoto.emerj.net or .staging.minamoto.emerj.net)
        if parsed.netloc:
            # Add leading dot for subdomain sharing
            domain = f".{parsed.netloc}" if not parsed.netloc.startswith(".") else parsed.netloc
        else:
            domain = None

        return {
            "domain": domain,
            "secure": True,  # HTTPS required for production/staging
            "samesite": "none",  # Required for cross-origin (different subdomains)
            "frontend_url": settings.APP_URL,
        }


@router.get("/login")
async def google_login(request: Request):
    """
    Redirect the user to Google's OAuth consent screen.
    Uses GOOGLE_REDIRECT_URI from settings.
    """
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    logger.info(f"Initiating Google login with redirect_uri: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Google OAuth callback:
    - Verify token
    - Create user if not exists
    - Generate JWT tokens
    - Set cookies dynamically based on environment (APP_URL or DEV_URL)
    - Redirect to appropriate frontend dashboard
    """
    try:
        # Exchange authorization code for tokens
        token = await oauth.google.authorize_access_token(request)
        id_token_str = token.get("id_token")

        if not id_token_str:
            raise HTTPException(status_code=400, detail="No id_token in token")

        user_info = id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), audience=settings.GOOGLE_CLIENT_ID
        )

        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email not found in token")

        logger.info(f"Google OAuth callback for email: {email}")

        user = await UserCRUD.get_by_email(db, email)
        if not user:
            user = await UserCRUD.create_google_user(
                db=db, email=email, name=user_info.get("name", email.split("@")[0])
            )

            await db.commit()
            await db.refresh(user)
            logger.info(f"Created new user via Google OAuth: {email}")

        if not user.is_active:
            logger.warning(f"Google login blocked: inactive account {email}")
            cookie_settings = get_cookie_settings(request)
            return RedirectResponse(
                url=f"{cookie_settings['frontend_url']}/login?error=account_inactive",
                status_code=302,
            )

        access_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
        )
        refresh_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=30),
        )

        # Store refresh token in Redis
        refresh_token_jti = get_token_jti(refresh_token)
        await _store_refresh_token(str(user.id), refresh_token_jti, ttl_days=30)

        # Get dynamic cookie settings based on request origin
        cookie_settings = get_cookie_settings(request)

        logger.info(
            f"Setting cookies for user {email}: "
            f"domain={cookie_settings['domain']}, "
            f"secure={cookie_settings['secure']}, "
            f"samesite={cookie_settings['samesite']}, "
            f"frontend_url={cookie_settings['frontend_url']}"
        )

        # Create redirect response to frontend dashboard
        response = RedirectResponse(
            url=f"{cookie_settings['frontend_url']}/dashboard/projects", status_code=302
        )

        # Set refresh token cookie (HTTP-only for security)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=cookie_settings["secure"],
            max_age=30 * 24 * 60 * 60,  # 30 days
            domain=cookie_settings["domain"],
            path="/",
            samesite=cookie_settings["samesite"],
        )

        # Set access token cookie (accessible to frontend)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=False,  # Frontend needs to read this
            secure=cookie_settings["secure"],
            max_age=24 * 60 * 60,  # 24 hours
            domain=cookie_settings["domain"],
            path="/",
            samesite=cookie_settings["samesite"],
        )

        logger.info(f"User {email} successfully logged in via Google OAuth")
        return response

    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he

    except Exception as e:
        logger.error("Google login failed: %s", str(e), exc_info=True)

        # Try to get cookie settings for error redirect
        try:
            cookie_settings = get_cookie_settings(request)
            frontend_url = cookie_settings["frontend_url"]
        except Exception:
            # Fallback to APP_URL if cookie settings fail
            frontend_url = settings.APP_URL

        return RedirectResponse(
            url=f"{frontend_url}/login?error=google_auth_failed&message={str(e)}", status_code=302
        )


async def _store_refresh_token(user_id: str, refresh_token_jti: str, ttl_days: int = 30) -> bool:
    """
    Store refresh token in Redis for token rotation.
    """
    try:
        redis_client = await get_redis_client()
        key = f"refresh_token:{user_id}:{refresh_token_jti}"
        await redis_client.setex(key, ttl_days * 24 * 3600, "valid")
        logger.info(f"Stored refresh token for user {user_id} (Google OAuth)")
        return True
    except Exception as e:
        logger.error(f"Failed to store refresh token: {str(e)}")
        return False
