import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    InviteParticipantsRequest,
    InviteParticipantsResponse,
)
from app.api.modules.v1.tickets.service.participant_service import ParticipantService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)


@router.post(
    "/{ticket_id}/invitations",
    response_model=InviteParticipantsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_participants(
    ticket_id: UUID,
    payload: InviteParticipantsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite participants to a ticket (BOTH internal users AND external participants).

    This UNIFIED endpoint handles both types of invitations automatically:

    **For Internal Users (existing in system):**
    - Sends notification email with regular ticket link
    - They log in normally to view the ticket
    - No expiration, full dashboard access
    - Email example: "john@yourcompany.com"

    **For External Participants (not in system):**
    - Creates guest access record
    - Generates secure JWT magic link
    - Sends email with magic link (/guest/access?token=xyz)
    - No login required, expires after expiry_days
    - Email example: "counsel@lawfirm.com"

    Args:
        ticket_id: UUID of the ticket
        payload: Request body with emails, role (for external), and expiry_days (for external)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        InviteParticipantsResponse with:
            - internal_users: List of notified internal users
            - external_participants: List of external participants with magic links
            - already_invited: List of emails already invited
    """
    try:
        # Get ticket to extract organization_id for billing check
        from sqlalchemy import select

        from app.api.modules.v1.tickets.models.ticket_model import Ticket

        ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = ticket_result.scalar_one_or_none()

        if not ticket:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Ticket not found",
            )

        # Check billing access for the organization
        try:
            await require_billing_access(organization_id=ticket.organization_id, db=db)
        except HTTPException as billing_error:
            logger.warning(
                f"Billing check failed for org {ticket.organization_id}: {billing_error.detail}"
            )
            raise billing_error

        service = ParticipantService(db)
        result = await service.invite_participants(
            ticket_id=ticket_id,
            emails=payload.emails,
            role=payload.role,
            expiry_days=payload.expiry_days,
            current_user_id=current_user.id,
        )

        logger.info(
            f"User {current_user.id} invited {len(result.internal_users)} internal users "
            f"and {len(result.external_participants)} external participants to ticket {ticket_id}"
        )

        message_parts = []
        if result.internal_users:
            message_parts.append(f"{len(result.internal_users)} internal user(s) notified")
        if result.external_participants:
            message_parts.append(
                f"{len(result.external_participants)} external participant(s) invited"
            )
        if result.already_invited:
            message_parts.append(f"{len(result.already_invited)} email(s) already invited")

        message = ". ".join(message_parts) if message_parts else "No changes made"

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message=message,
            data=result.model_dump(),
        )

    except ValueError as e:
        logger.warning(
            f"Validation error in invite_participants: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error inviting participants: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to invite participants. Please try again.",
        )
