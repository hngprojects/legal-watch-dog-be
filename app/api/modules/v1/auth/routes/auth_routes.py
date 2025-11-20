"""Authentication"""

import logging
import uuid

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
from app.api.utils.response_payloads import (
    fail_response,
    success_response,
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
    and sends OTP email (in background to avoid blocking).
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
                data={
                    "errors": {"email": ["Email already in use"]},
                    "trace_id": str(uuid.uuid4()),
                },
            )
        user = await register_organization(
            db, payload, background_tasks=background_tasks
        )
    except Exception:
        logger.exception("Error during registration for email=%s", payload.email)
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Registration failed. Please contact support.",
            data={
                "errors": {"email": ["Failed to register account"]},
                "trace_id": str(uuid.uuid4()),
            },
        )

    logger.info(
        "Registration succeeded for email=%s, user_id=%s",
        payload.email,
        getattr(user, "id", None),
    )
    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Registration successful. Verify the OTP sent to your email and login.",
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
            data={
                "errors": {"email": ["Failed to verify OTP"]},
                "trace_id": str(uuid.uuid4()),
            },
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
            data={
                "errors": {"email": ["User account not found"]},
                "trace_id": str(uuid.uuid4()),
            },
        )

    logger.info(
        "OTP verification succeeded for email=%s, user_id=%s", payload.email, user.id
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Email verified",
        data={"email": user.email},
    )
