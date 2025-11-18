"""Authentication"""

import logging
from fastapi import APIRouter, status, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.modules.v1.auth.service.register_service import register_organization
from app.api.modules.v1.auth.schemas.register import RegisterRequest, RegisterResponse
from app.api.utils.response_payloads import (
    auth_response,
    fail_response,
)
from app.api.db.database import get_db


router = APIRouter(prefix="/auth", tags=["Auth"])

logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def company_signup(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Company sign-up: creates organization, admin role, admin user, stores OTP in Redis
    and sends OTP email (sent in background to avoid blocking).
    """
    logger.info("Starting company signup for email=%s", payload.email)
    try:
        user, access_token = await register_organization(
            db, payload, background_tasks=background_tasks
        )
    except Exception:
        logger.exception("Error during registration for email=%s", payload.email)
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Registration failed. Please contact support.",
        )

    if not user or not access_token:
        logger.error(
            "Registration did not return user/token for email=%s (user=%s, token=%s)",
            payload.email,
            bool(user),
            bool(access_token),
        )
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Registration failed. Missing account data.",
        )

    logger.info(
        "Registration succeeded for email=%s, user_id=%s",
        payload.email,
        getattr(user, "id", None),
    )
    return auth_response(
        status_code=status.HTTP_201_CREATED,
        message="Registration successful. Verify the OTP sent to your email.",
        access_token=access_token,
        data={"email": user.email},
    )
