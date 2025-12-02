import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)
from app.api.modules.v1.waitlist.service.waitlist_service import waitlist_service
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])
logger = logging.getLogger("app")


@router.post("/signup", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
async def signup_waitlist(
    signup: WaitlistSignup,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a user to the waitlist.

    Validates:
    - organization_email: Must be a valid, real email address (not test/dummy/disposable emails)
    - organization_name: Must contain only letters, spaces, and common punctuation (no numbers)

    Returns:
    - 201: Successfully added to waitlist
    - 422: Validation error (invalid email or organization name format)
    - 400: Duplicate email
    - 500: Server error
    """
    try:
        result = await waitlist_service.add_to_waitlist(db, signup)

        background_tasks.add_task(waitlist_service._send_confirmation_email, signup)

        return success_response(
            201,
            "Successfully added to waitlist. Confirmation email will be sent shortly.",
            data=result.model_dump(),
        )
    except HTTPException as e:
        logger.warning(
            f"Waitlist signup failed - Email: {signup.organization_email}, "
            f"Status: {e.status_code}, Reason: {e.detail}"
        )
        return error_response(status_code=e.status_code, message=e.detail)
    except Exception as e:
        logger.error(
            f"Unexpected error during waitlist signup - Email: {signup.organization_email}, "
            f"Error: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred. Please try again later.",
        )
