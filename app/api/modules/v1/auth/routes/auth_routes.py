"""Authentication"""

import logging
from fastapi import APIRouter, status, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.modules.v1.auth.service.register_service import (
    register_organization,
    verify_otp as service_verify_otp,
    get_organisation_by_email,
)
from app.api.modules.v1.auth.schemas.register import (
    RegisterRequest,
    RegisterResponse,
    OTPVerifyRequest,
)
from sqlmodel import select
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import (
    fail_response,
    success_response,
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
        organization = await get_organisation_by_email(db, payload.email)
        if organization:
            logger.warning(
                "Registration attempt with existing organization email=%s",
                payload.email,
            )
            return fail_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="An organization with this email already exists.",
            )
        user = await register_organization(
            db, payload, background_tasks=background_tasks
        )
    except Exception:
        logger.exception("Error during registration for email=%s", payload.email)
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Registration failed. Please contact support.",
        )

    logger.info(
        "Registration succeeded for email=%s, user_id=%s",
        payload.email,
        getattr(user, "id", None),
    )
    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Registration successful. Verify your email and log in.",
        data={"email": user.email},
    )


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp_endpoint(
    payload: OTPVerifyRequest, db: AsyncSession = Depends(get_db)
):
    """Verify OTP sent to user email and return final access token."""
    logger.info("Verifying OTP for email=%s", payload.email)

    ok = await service_verify_otp(db, payload.email, payload.code)
    if not ok:
        logger.warning("OTP verification failed for email=%s", payload.email)
        return fail_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Invalid or expired code",
        )

    # Fetch user to create final token
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user:
        logger.error(
            "User not found after successful OTP verification: %s", payload.email
        )
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Verification succeeded but user record missing. Contact support.",
        )

    logger.info(
        "OTP verification succeeded for email=%s, user_id=%s", payload.email, user.id
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Email verified successfully. You can now log in.",
        data={"email": user.email},
    )
