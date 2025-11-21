import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)
from app.api.modules.v1.waitlist.service.waitlist_service import waitlist_service
from app.api.utils.response_payloads import fail_response, success_response

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
    -organization_email: Valid organization email address to add to waitlist
    -organization_name: Name of the organization
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
        return fail_response(e.status_code, e.detail)
