import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.ticket_invitation_schema import (
    InviteUsersToTicketRequest,
    InviteUsersToTicketResponse,
)
from app.api.modules.v1.tickets.service.ticket_service import TicketService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    dependencies=[Depends(require_billing_access)],
)


@router.post(
    "/{ticket_id}/invitations",
    response_model=InviteUsersToTicketResponse,
    status_code=status.HTTP_200_OK,
)
async def invite_users_to_ticket(
    ticket_id: UUID,
    payload: InviteUsersToTicketRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite users to collaborate on a ticket by their email addresses.

    This endpoint allows owners and admins to invite organization members to a ticket.
    Invited users will receive an email notification with a link to the ticket.

    Requirements:
        - User must be authenticated
        - User must have INVITE_PARTICIPANTS permission (Owner or Admin role)
        - User must be a member of the ticket's organization
        - Emails must belong to verified, active members of the organization
        - Ticket must exist

    Args:
        ticket_id: UUID of the ticket to invite users to
        payload: Request body containing list of email addresses
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        InviteUsersToTicketResponse containing:
            - invited: List of successfully invited users with details
            - already_invited: List of emails that were already invited
            - not_found: List of emails not found in the organization
    """
    try:
        service = TicketService(db)
        result = await service.invite_users_to_ticket(
            ticket_id=ticket_id,
            emails=payload.emails,
            current_user_id=current_user.id,
        )

        logger.info(
            f"User {current_user.id} invited {len(result.invited)} users to ticket {ticket_id}"
        )

        invited_count = len(result.invited)
        message_parts = []

        if invited_count > 0:
            message_parts.append(f"{invited_count} user(s) invited successfully")
        if result.already_invited:
            message_parts.append(f"{len(result.already_invited)} user(s) already invited")
        if result.not_found:
            message_parts.append(f"{len(result.not_found)} email(s) not found in organization")

        message = ". ".join(message_parts) if message_parts else "No changes made"

        return success_response(
            status_code=status.HTTP_200_OK,
            message=message,
            data=result.model_dump(),
        )

    except ValueError as e:
        logger.warning(
            f"Validation error in invite_users_to_ticket: {str(e)}",
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
            f"Error inviting users to ticket: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="Failed to invite users to ticket. Please try again.",
        )
