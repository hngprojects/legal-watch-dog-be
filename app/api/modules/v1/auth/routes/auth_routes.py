import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, status
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.registeration_redis import get_redis
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
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.response_payloads import (
    error_response,
    success_response,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses=company_signup_responses,  # type: ignore
)
async def company_signup(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
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
        result = await service.register_user(payload, background_tasks)

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


company_signup._custom_errors = company_signup_custom_errors  # type: ignore
company_signup._custom_success = company_signup_custom_success  # type: ignore


@router.post(
    "/otp/verification",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_201_CREATED,
    responses=verify_otp_responses,  # type: ignore
)
async def verify_otp(
    payload: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Verify OTP and complete company registration.

    Validates the one-time password sent to the user's email and completes the
    registration process by creating the organization, admin role, and admin user account.

    Args:
        payload (VerifyOTPRequest): Object containing email and OTP code.
        db (AsyncSession, optional): Async database session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP validation
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response indicating OTP verification status.
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
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))

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


verify_otp._custom_errors = verify_otp_custom_errors  # type: ignore
verify_otp._custom_success = verify_otp_custom_success  # type: ignore


@router.post(
    "/otp/requests",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
    responses=request_new_otp_responses,  # type: ignore
)
async def request_new_otp(
    payload: ResendOTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Resend OTP for pending registration.

    Generates and sends a new OTP code to an email address with a pending registration
    that has not yet completed verification. The previous OTP is invalidated.

    Args:
        payload (ResendOTPRequest): Object containing the email to resend OTP for.
        background_tasks (BackgroundTasks): FastAPI background tasks instance for async operations.
        db (AsyncSession, optional): Async database session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP management.
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response containing OTP resend status.
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
        return error_response(
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
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Failed to resend OTP. Please try again later.",
        )


request_new_otp._custom_errors = request_new_otp_custom_errors  # type: ignore
request_new_otp._custom_success = request_new_otp_custom_success  # type: ignore


@router.get(
    "/accept-invite/{token}",
    status_code=status.HTTP_200_OK,
    response_model=dict,
)
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept an organization invitation.

    This endpoint handles the invitation link sent to a user.
    It validates the token, adds the user to the organization (if registered),
    or redirects them to registration (if unregistered).

    Args:
        token: The unique invitation token.
        db: Database session dependency.

    Returns:
        dict: Success message or a redirect (handled by frontend).

    Raises:
        HTTPException: 400, 404, 410, 500 for server errors.
    """
    try:
        invitation = await InvitationCRUD.get_invitation_by_token(db, token)
        if not invitation:
            raise ValueError("Invitation not found or invalid.")

        if invitation.status != "pending":
            raise ValueError(f"Invitation is already {invitation.status}.")

        if invitation.expires_at < datetime.now(timezone.utc):
            await InvitationCRUD.update_invitation_status(db, invitation.id, "expired")
            await db.commit()
            raise ValueError("Invitation has expired.")

        user = await UserCRUD.get_by_email(db, invitation.invited_email)

        if user:
            # User is already registered
            # Check if user is already a member of the organization
            existing_membership = await UserOrganizationCRUD.get_user_organization(
                db, user.id, invitation.organization_id
            )
            if existing_membership:
                await InvitationCRUD.update_invitation_status(db, invitation.id, "accepted")
                await db.commit()
                return success_response(
                    status_code=status.HTTP_200_OK,
                    message="You are already a member of this organization. Invitation accepted.",
                    data={"organization_id": str(invitation.organization_id)},
                )

            # Add user to the organization
            role_id = invitation.role_id
            if not role_id:
                # Get default member role if not specified in invitation
                default_role = await RoleCRUD.get_default_user_role(db, invitation.organization_id)
                role_id = default_role.id

            await UserOrganizationCRUD.add_user_to_organization(
                db=db,
                user_id=user.id,
                organization_id=invitation.organization_id,
                role_id=role_id,
                is_active=True,
            )
            await InvitationCRUD.update_invitation_status(db, invitation.id, "accepted")
            await db.commit()

            return success_response(
                status_code=status.HTTP_200_OK,
                message="Invitation accepted. You have been added to the organization.",
                data={"organization_id": str(invitation.organization_id)},
            )
        else:
            # User is not registered. Redirect to registration with token.
            # Frontend should handle the redirect to a registration page,
            # passing the token as a query parameter.
            registration_url = f"{settings.DEV_URL}/register?token={token}"
            # In a real scenario, you'd return a redirect response here.
            # For FastAPI, this might involve a RedirectResponse from fastapi.responses
            # For now, we'll just return a message indicating the redirect.
            logger.info(f"Unregistered user. Redirecting to: {registration_url}")
            return success_response(
                status_code=status.HTTP_200_OK,
                message="Please register to accept the invitation.",
                data={"redirect_url": registration_url},
            )

    except ValueError as e:
        logger.warning(f"Invitation acceptance failed for token={token}: {str(e)}")
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "expired" in error_message.lower():
            status_code = status.HTTP_410_GONE
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
