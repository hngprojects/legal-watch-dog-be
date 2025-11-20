"""Authentication"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas.register import (
    OTPVerifyRequest,
    RegisterRequest,
    RegisterResponse,
)
from app.api.modules.v1.auth.service.register_service import (
    get_organisation_by_email,
    register_organization,
)
from app.api.modules.v1.auth.service.register_service import (
    verify_otp as service_verify_otp,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import create_access_token
from app.api.utils.response_payloads import (
    auth_response,
    fail_response,
)

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
        data={"email": user.email},
        access_token=access_token,
    )


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp_endpoint(payload: OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
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
        logger.error("User not found after successful OTP verification: %s", payload.email)
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Verification succeeded but user record missing. Contact support.",
        )

    # Create a final access token now that the user is verified
    access_token = create_access_token(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        role_id=str(user.role_id),
    )

    logger.info("OTP verification succeeded for email=%s, user_id=%s", payload.email, user.id)
    return auth_response(
        status_code=status.HTTP_200_OK,
        message="Email verified",
        access_token=access_token,
        data={"email": user.email},
    )
