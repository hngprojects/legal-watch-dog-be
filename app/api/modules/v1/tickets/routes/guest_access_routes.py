import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.tickets.dependencies.guest_auth import (
    GuestContext,
    get_current_guest,
)
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    GuestTicketAccessResponse,
)
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets/external",
    tags=["Tickets"],
)


@router.get(
    "/access",
    response_model=GuestTicketAccessResponse,
    status_code=status.HTTP_200_OK,
)
async def get_guest_ticket_access(
    guest: GuestContext = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate guest access token and return ticket details.

    This endpoint is called when a guest clicks the magic link.
    It validates their token and returns the ticket they can access.

    CRITICAL SECURITY:
        - Token signature is validated
        - Token audience must be "guest_access"
        - ExternalParticipant must be active
        - Ticket must be open (not closed)
        - Token ticket_id must match the participant's ticket

    NO LOGIN REQUIRED - Uses Bearer token from magic link.

    Args:
        guest: Guest context from token validation (injected)
        db: Database session (injected)

    Returns:
        GuestTicketAccessResponse with limited ticket information
    """
    try:
        ticket = guest.ticket
        participant = guest.participant

        response_data = GuestTicketAccessResponse(
            ticket_id=str(ticket.id),
            title=ticket.title,
            description=ticket.description,
            priority=ticket.priority.value,
            status=ticket.status.value,
            created_at=ticket.created_at,
            project_name=ticket.project.title if ticket.project else None,
            participant_email=participant.email,
            participant_role=participant.role,
            access_expires_at=participant.expires_at,
        )

        logger.info(
            f"Guest {participant.email} successfully accessed ticket {ticket.id}"
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Guest access validated successfully",
            data=response_data.model_dump(),
        )

    except Exception as e:
        logger.error(
            f"Error in guest ticket access: {str(e)}",
            exc_info=True,
            extra={
                "participant_id": str(guest.participant_id),
                "ticket_id": str(guest.ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to load ticket. Please try again or contact support.",
        )
