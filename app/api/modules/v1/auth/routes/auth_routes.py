import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.redis_service import check_rate_limit
from app.api.core.dependencies.registeration_redis import get_redis
from app.api.core.exceptions import RateLimitExceeded
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.auth_routes_docs import (
    company_signup_custom_errors,
    company_signup_custom_success,
    company_signup_responses,
    request_new_otp_custom_errors,
    request_new_otp_custom_success,
    request_new_otp_responses,
    verify_otp_custom_errors,
    verify_otp_custom_success,
    verify_otp_responses,
)
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
from app.api.modules.v1.organization.models.invitation_model import InvitationStatus
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.response_payloads import (
    error_response,
    success_response,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

logger = logging.getLogger("app")

MAX_OTP_REQUEST_ATTEMPTS = 3
MAX_OTP_VERIFY_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600
IP_RATE_LIMIT_MULTIPLIER = 3


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses=company_signup_responses,
)
async def company_signup(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
    token: Optional[str] = None,
):
    """
    Initiate company registration with email verification.

    Creates a pending registration, generates an OTP, and sends it to the provided
    email address. Actual organization and user creation occurs after OTP verification.

    Args:
        payload (RegisterRequest): Registration details including name, email, and password.
        background_tasks (BackgroundTasks): FastAPI background tasks instance for async operations.
        db (AsyncSession, optional): Async SQLAlchemy session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP management.
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response with status, message, and data/error details.
    """
    try:
        service = RegistrationService(db, redis_client)
        result = await service.register_user(payload, background_tasks, token)

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Registration initiated. Verify the OTP sent to your email.",
            data=result,
        )

    except ValueError as e:
        logger.warning("Registration validation failed for email=%s: %s", payload.email, str(e))
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))

    except Exception as e:
        logger.error(
            "Failed to process registration for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Registration failed. Please try again later.",
        )


company_signup._custom_errors = company_signup_custom_errors
company_signup._custom_success = company_signup_custom_success


@router.post(
    "/otp/verification",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_201_CREATED,
    responses=verify_otp_responses,
)
async def verify_otp(
    payload: VerifyOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Verify OTP and complete company registration.

    Validates the one-time password sent to the user's email and completes the
    registration process by creating the organization, admin role, and admin user account.

    Rate Limited:
    - Maximum 5 verification attempts per hour per email.
    - Maximum 15 verification attempts per hour per IP address.

    Args:
        payload (VerifyOTPRequest): Object containing email and OTP code.
        db (AsyncSession, optional): Async database session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP validation
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response indicating OTP verification status.

    Raises:
        RateLimitExceeded: If the email or IP exceeds the allowed number of verification attempts.
        ValueError: If the OTP is invalid or expired.
        HTTPException: 500 for internal server errors.
    """
    try:
        email_allowed = await check_rate_limit(
            f"otp_verify:email:{payload.email}",
            max_attempts=MAX_OTP_VERIFY_ATTEMPTS,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )

        if not email_allowed:
            raise RateLimitExceeded(
                retry_after=RATE_LIMIT_WINDOW_SECONDS,
                detail="Too many OTP verification attempts for this email. Please retry in 1 hour.",
            )

        ip_address = request.client.host if request.client else None

        if ip_address:
            ip_allowed = await check_rate_limit(
                f"otp_verify:ip:{ip_address}",
                max_attempts=MAX_OTP_VERIFY_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

        if not ip_allowed:
            raise RateLimitExceeded(
                retry_after=RATE_LIMIT_WINDOW_SECONDS,
                detail="Too many OTP verification attempts from this IP. Please retry in 1 hour.",
            )

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
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))

    except RateLimitExceeded:
        raise

    except Exception as e:
        logger.error(
            "Failed to verify OTP for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="OTP verification failed. Please try again later.",
        )


verify_otp._custom_errors = verify_otp_custom_errors
verify_otp._custom_success = verify_otp_custom_success


@router.post(
    "/otp/requests",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
    responses=request_new_otp_responses,
)
async def request_new_otp(
    payload: ResendOTPRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Resend OTP for pending registration.

    Generates and sends a new OTP code to an email address with a pending registration
    that has not yet completed verification. The previous OTP is invalidated.

    Rate Limited:
    - Maximum 3 requests per hour per email.
    - Maximum 9 requests per hour per IP address.

    Args:
        payload (ResendOTPRequest): Object containing the email to resend OTP for.
        background_tasks (BackgroundTasks): FastAPI background tasks instance for async operations.
        db (AsyncSession, optional): Async database session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP management.
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response containing OTP resend status.

    Raises:
        RateLimitExceeded: If the email or IP exceeds the allowed number of requests.
        HTTPException: 400 for validation errors or 500 for internal server errors.
    """
    try:
        email_allowed = await check_rate_limit(
            f"otp_request:email:{payload.email}",
            max_attempts=MAX_OTP_REQUEST_ATTEMPTS,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )

        if not email_allowed:
            raise RateLimitExceeded(
                retry_after=RATE_LIMIT_WINDOW_SECONDS,
                detail="Too many OTP requests for this email. Please retry in 1 hour.",
            )

        ip_address = request.client.host if request.client else None

        if ip_address:
            ip_allowed = await check_rate_limit(
                f"otp_request:ip:{ip_address}",
                max_attempts=MAX_OTP_REQUEST_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

            if not ip_allowed:
                raise RateLimitExceeded(
                    retry_after=RATE_LIMIT_WINDOW_SECONDS,
                    detail="Too many OTP requests from this IP. Please retry in 1 hour.",
                )

        service = RegistrationService(db, redis_client)
        result = await service.resend_otp(
            email=payload.email,
            background_tasks=background_tasks,
        )

        minutes = settings.REDIS_RESEND_TTL / 60
        minutes_display = int(minutes) if minutes.is_integer() else round(minutes, 2)
        unit = "minute" if minutes_display == 1 else "minutes"
        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"A new OTP has been sent to your email, expiring in {minutes_display} {unit}.",
            data=result,
        )

    except ValueError as e:
        logger.warning("Resend OTP validation failed for email=%s: %s", payload.email, str(e))
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )

    except RateLimitExceeded:
        raise

    except Exception as e:
        logger.error(
            "Failed to resend OTP for email=%s: %s",
            payload.email,
            str(e),
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Failed to resend OTP. Please try again later.",
        )


request_new_otp._custom_errors = request_new_otp_custom_errors
request_new_otp._custom_success = request_new_otp_custom_success


@router.post(
    "/invitations/{token}/accept",
    status_code=status.HTTP_302_FOUND,
    response_model=None,
)
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Accept an organization invitation.

    This endpoint handles invitation acceptance for both registered and unregistered users:
    - Registered & authenticated users: Validates email match and adds to organization
    - Unregistered users or unauthenticated: Redirects to registration page with token

    SECURITY: For authenticated users, validates that their email matches the invitation's
    invited_email to prevent unauthorized access.

    Args:
        token: The unique invitation token.
        db: Database session dependency.
        current_user: The authenticated user (optional, from JWT token if provided).

    Returns:
        dict: Success response (200) for authenticated users with organization details
        RedirectResponse: Redirect (302) for unauthenticated users to signup page

    Raises:
        HTTPException:
            - 400: Bad request (general validation errors)
            - 403: Forbidden (authenticated user's email doesn't match invitation)
            - 404: Not found (invalid invitation token)
            - 410: Gone (expired invitation)
            - 500: Internal server error (unexpected errors)
    """
    try:
        try:
            user_from_token = current_user
        except HTTPException:
            user_from_token = None

        invitation = await InvitationCRUD.get_invitation_by_token(db, token)
        if not invitation:
            raise ValueError("Invitation not found or invalid.")

        if invitation.status != InvitationStatus.PENDING:
            raise ValueError(f"Invitation is already {invitation.status}.")

        if invitation.expires_at < datetime.now(timezone.utc):
            await InvitationCRUD.update_invitation_status(
                db, invitation.id, InvitationStatus.EXPIRED
            )
            await db.commit()
            raise ValueError("Invitation has expired.")

        user = await UserCRUD.get_by_email(db, invitation.invited_email)

        if user and user_from_token:
            if user_from_token.email.lower() != invitation.invited_email.lower():
                logger.warning(
                    f"Unauthorized invitation acceptance attempt: user={user_from_token.email}, "
                    f"invited={invitation.invited_email}, token={token}"
                )
                raise ValueError(
                    "This invitation was sent to a different email address. "
                    "You can only accept invitations sent to your email."
                )

            existing_membership = await UserOrganizationCRUD.get_user_organization(
                db, user_from_token.id, invitation.organization_id
            )
            if existing_membership:
                await InvitationCRUD.update_invitation_status(
                    db, invitation.id, InvitationStatus.ACCEPTED
                )
                await db.commit()
                return success_response(
                    status_code=status.HTTP_200_OK,
                    message="You are already a member of this organization. Invitation accepted.",
                    data={"organization_id": str(invitation.organization_id)},
                )

            role_id = invitation.role_id
            if not role_id:
                default_role = await RoleCRUD.get_default_user_role(db, invitation.organization_id)
                role_id = default_role.id

            await UserOrganizationCRUD.add_user_to_organization(
                db=db,
                user_id=user_from_token.id,
                organization_id=invitation.organization_id,
                role_id=role_id,
                is_active=True,
            )
            await InvitationCRUD.update_invitation_status(
                db, invitation.id, InvitationStatus.ACCEPTED
            )
            await db.commit()

            logger.info(
                f"Invitation accepted: user={user_from_token.email}, "
                f"org_id={invitation.organization_id}, token={token}"
            )

            return success_response(
                status_code=status.HTTP_302_FOUND,
                message="Invitation accepted. You have been added to the organization.",
                data={
                    "organization_id": str(invitation.organization_id),
                    "organization_name": invitation.organization_name,
                    "role_name": invitation.role_name,
                },
            )
        else:
            registration_url = f"{settings.APP_URL}/signup?token={token}"
            logger.info(
                "Unregistered/unauthenticated user for invitation. "
                f"Redirecting to: {registration_url}"
            )
            return RedirectResponse(url=registration_url, status_code=status.HTTP_302_FOUND)

    except ValueError as e:
        logger.warning(f"Invitation acceptance failed for token={token}: {str(e)}")
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "expired" in error_message.lower():
            status_code = status.HTTP_410_GONE
        elif "different email" in error_message.lower() or "only accept" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Unexpected error accepting invitation for token={token}: {str(e)}",
            exc_info=True,
        )
        await db.rollback()
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to accept invitation. Please try again later.",
        )
