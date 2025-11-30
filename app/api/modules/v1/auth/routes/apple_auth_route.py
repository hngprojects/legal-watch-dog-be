import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas.apple_auth import AppleAuthRequest
from app.api.modules.v1.auth.service.apple_auth import AppleAuthClient
from app.api.utils.cookie_helper import set_auth_cookies
from app.api.utils.response_payloads import auth_response, error_response, success_response

router = APIRouter(prefix="/auth/apple", tags=["Social Auth"])
logger = logging.getLogger("app")


@router.post("/signin")
async def apple_login(
    req: AppleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Apple sign-in.

    Accepts an authorization code from the frontend, completes the OAuth flow,
    and returns a JWT access token along with user info.
    """
    apple_client = AppleAuthClient(db)

    try:
        result = await apple_client.complete_oauth_flow(
            code=req.code, redirect_uri=req.redirect_uri or settings.APPLE_REDIRECT_URI
        )


        # response.set_cookie(
        #     key="access_token",
        #     value=result["access_token"],
        #     httponly=True,
        #     max_age=3600,
        #     secure=settings.ENVIRONMENT != "dev",
        #     samesite="lax",
        #     path="/",
        # )

        # Set authentication cookies using centralized utility
        # Note: Apple OAuth only returns access_token, no refresh_token
        set_auth_cookies(
            response=response,
            request=request,
            access_token=result["access_token"],
            refresh_token=None,
        )

        return auth_response(
            status_code=200,
            message="Apple login successful",
            access_token=result["access_token"],
            data={
                "user_id": result["user_id"],
                "email": result["email"],
                "is_new_user": result["is_new_user"],
            },
        )

    except ValueError as e:
        logger.warning(f"Apple login failed due to invalid data: {e}")
        return error_response(status_code=400, message=str(e), error="invalid_request")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during Apple login: {e}")
        return error_response(
            status_code=500,
            message="An internal server error occurred during login.",
            error="server_error",
        )


@router.post("/callback")
async def apple_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    code: str = Form(...),
):
    """
    Callback endpoint for Apple OAuth.

    Receives POST data from Apple after user login, completes the OAuth flow,
    and returns JWT access token and user details.
    """
    apple_client = AppleAuthClient(db)
    try:
        result = await apple_client.complete_oauth_flow(
            code=code, redirect_uri=settings.APPLE_REDIRECT_URI
        )

        set_auth_cookies(
            response=response,
            access_token=result["access_token"],
            refresh_token=None,
            request=request,
        )

        return success_response(status_code=200, message="Login successful", data=result)
    except ValueError as e:
        logger.warning(f"Apple callback failed due to invalid data: {e}")
        return error_response(status_code=400, message=str(e), error="invalid_request")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during Apple callback: {e}")
        return error_response(
            status_code=500, message="An internal server error occurred.", error="server_error"
        )
