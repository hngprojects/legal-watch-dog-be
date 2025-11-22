import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.registeration_redis import get_redis
from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas.register import (
    RegisterRequest,
    RegisterResponse,
)
from app.api.modules.v1.auth.schemas.resend_otp import ResendOTPRequest
from app.api.modules.v1.auth.schemas.verify_otp import (
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.api.modules.v1.auth.service.register_service import RegistrationService
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
    redis_client: Redis = Depends(get_redis),
):
    """
    Company sign-up endpoint.

    Initiates the company registration process by validating the email,
    generating an OTP, and sending verification email. The actual organization
    and user creation happens after OTP verification.

    Args:
        payload: Registration request with email, password, name, industry
        background_tasks: FastAPI background tasks for async operations
        db: Database session dependency
        redis_client: Redis client dependency

    Returns:
        RegisterResponse: Success response with registration details

    Raises:
        HTTPException: 400 for validation errors, 500 for server errors
    """
    try:
        service = RegistrationService(db, redis_client)
        result = await service.register_company(payload, background_tasks)

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Registration initiated. Verify the OTP sent to your email.",
            data=result,
        )

    except ValueError as e:
        logger.warning("Registration validation failed for email=%s: %s", payload.email, str(e))
        return fail_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))

    except Exception as e:
        logger.error(
            "Failed to process registration for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Registration failed. Please try again later.",
        )


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_otp(
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Verify OTP and complete company registration.

    Validates the OTP code sent to the user's email and completes the
    registration by creating the organization, admin role, and admin user.

    Args:
        payload: OTP verification request with email and code
        db: Database session dependency
        redis_client: Redis client dependency

    Returns:
        VerifyOTPResponse: Success response with organization and user details

    Raises:
        HTTPException: 400 for invalid OTP, 500 for server errors
    """
    try:
        service = RegistrationService(db, redis_client)
        result = await service.verify_otp_and_complete_registration(
            email=payload.email, code=payload.code
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Registration completed successfully",
            data=result,
        )

    except ValueError as e:
        return fail_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))

    except Exception as e:
        logger.error(
            "Failed to verify OTP for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="OTP verification failed. Please try again later.",
        )


@router.post(
    "/resend-otp",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
)
async def resend_otp(
    payload: ResendOTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Resend registration OTP for a pending signup.

    Handles resending an OTP to an email that has already started
    registration but has not yet completed verification.

    Args:
        payload: Request body containing the email address to resend OTP to.
        background_tasks: FastAPI background task handler for sending email asynchronously.
        db: Database session dependency.
        redis_client: Redis client dependency used to look up pending registrations.

    Returns:
        RegisterResponse: Success response including the registered email address.

    Raises:
        HTTPException: 400 if validation fails (no pending registration, already registered),
                       500 for unexpected server errors.
    """
    try:
        service = RegistrationService(db, redis_client)
        result = await service.resend_otp(
            email=payload.email,
            background_tasks=background_tasks,
        )

        minutes = settings.REDIS_CACHE_TTL_SECONDS / 60
        minutes_display = int(minutes) if minutes.is_integer() else round(minutes, 2)
        unit = "minute" if minutes_display == 1 else "minutes"
        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"A new OTP has been sent to your email, expiring in {minutes_display} {unit}.",
            data=result,
        )

    except ValueError as e:
        logger.warning("Resend OTP validation failed for email=%s: %s", payload.email, str(e))
        return fail_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except Exception as e:
        logger.error(
            "Failed to resend OTP for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to resend OTP. Please try again later.",
        )
