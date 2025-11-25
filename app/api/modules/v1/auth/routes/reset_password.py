import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.exceptions import PasswordReuseError
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.reset_password_docs import (
    confirm_reset_custom_errors,
    confirm_reset_custom_success,
    confirm_reset_responses,
    request_reset_custom_errors,
    request_reset_custom_success,
    request_reset_responses,
    verify_reset_custom_errors,
    verify_reset_custom_success,
    verify_reset_responses,
)
from app.api.modules.v1.auth.schemas.reset_password import (
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetVerify,
)
from app.api.modules.v1.auth.service.reset_password import (
    request_password_reset as service_request_reset,
)
from app.api.modules.v1.auth.service.reset_password import (
    reset_password as service_reset_password,
)
from app.api.modules.v1.auth.service.reset_password import (
    verify_reset_code as service_verify_code,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/password", tags=["Auth"])


@router.post(
    "/resets",
    status_code=status.HTTP_200_OK,
    responses=request_reset_responses,  # type: ignore
    response_model=PasswordResetRequest,
)
async def request_password_reset(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset for a user.

    - Validates the email address.
    - Generates a One-Time Password (OTP) and stores it securely.
    - Sends the OTP to the user's email.

    Args:
        payload (PasswordResetRequest): Contains the user's email.
        background_tasks (BackgroundTasks): For sending the email asynchronously.
        db (AsyncSession): Database session dependency.

    Returns:
        JSON response confirming whether the reset code was sent.
    """
    logger.info("Password reset requested for email=%s", payload.email)

    try:
        user = await db.scalar(select(User).where(User.email == payload.email))

        if not user:
            logger.warning("Password reset requested for non-existent email=%s", payload.email)
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Email does not exist.",
            )

        if not user.is_active:
            logger.warning("Password reset requested for inactive user: email=%s", payload.email)
            return error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Account is inactive. Please contact support.",
            )

        await service_request_reset(db, user, background_tasks)

        logger.info("Password reset code sent for email=%s, user_id=%s", payload.email, user.id)
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Reset code sent to email.",
            data={"email": user.email},
        )

    except Exception:
        logger.exception("Error during password reset request for email=%s", payload.email)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="INTERNAL_SERVER_ERROR",
            message="Password reset request failed",
        )


request_password_reset._custom_errors = request_reset_custom_errors  # type: ignore
request_password_reset._custom_success = request_reset_custom_success  # type: ignore


@router.post(
    "/resets/verification",
    status_code=status.HTTP_200_OK,
    responses=verify_reset_responses,  # type: ignore
    response_model=PasswordResetVerify,
)
async def verify_reset_code(
    payload: PasswordResetVerify,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the OTP code sent to user's email.

    - Validates the provided code.
    - Returns a temporary reset token if valid.

    Args:
        payload (PasswordResetVerify): Contains email and OTP code.
        db (AsyncSession): Database session dependency.

    Returns:
        JSON response containing the temporary reset token.
    """
    logger.info("Verifying password reset code for email=%s", payload.email)

    try:
        reset_token = await service_verify_code(db, payload.email, payload.code)

        if not reset_token:
            logger.warning("Invalid or expired reset code for email=%s", payload.email)
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invalid or expired token.",
            )

        logger.info("Reset code verified for email=%s", payload.email)
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Token verified successfully.",
            data={"reset_token": reset_token},
        )

    except Exception:
        logger.exception("Error verifying reset code for email=%s", payload.email)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error.",
        )


verify_reset_code._custom_errors = verify_reset_custom_errors  # type: ignore
verify_reset_code._custom_success = verify_reset_custom_success  # type: ignore


@router.post(
    "/resets/confirmation",
    status_code=status.HTTP_200_OK,
    responses=confirm_reset_responses,  # type: ignore
    response_model=PasswordResetConfirm,
)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm and reset the user's password using the temporary token.

    - Validates the temporary reset token.
    - Updates the user's password.
    - Prevents reuse of previous passwords.

    Args:
        payload (PasswordResetConfirm): Contains `reset_token` and `new_password`.
        db (AsyncSession): Database session dependency.

    Returns:
        JSON response confirming password reset success or failure.
    """
    logger.info("Confirming password reset for reset_token=%s", payload.reset_token[:10])

    try:
        success = await service_reset_password(db, payload.reset_token, payload.new_password)

        if not success:
            logger.warning("Invalid or expired reset token")
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invalid or expired reset token.",
            )

        logger.info("Password reset completed successfully")
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Password reset successful.",
        )

    except PasswordReuseError as e:
        logger.warning("Password reuse attempt during reset: %s", str(e))
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Cannot reuse old password.",
        )

    except Exception:
        logger.exception("Error confirming password reset")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error.",
        )


confirm_password_reset._custom_errors = confirm_reset_custom_errors  # type: ignore
confirm_password_reset._custom_success = confirm_reset_custom_success  # type: ignore
