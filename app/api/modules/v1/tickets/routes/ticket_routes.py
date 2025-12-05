"""
Ticket Routes
API endpoints for ticket management operations.

This module provides RESTful endpoints for ticket operations,
including closing tickets and other ticket state management.
All endpoints require authentication and enforce organization-level
access control.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import (
    TicketCloseRequest,
    TicketResponse,
)
from app.api.modules.v1.tickets.service.close_ticket_service import TicketService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

router = APIRouter(
    prefix="/organizations/{organization_id}/projects/{project_id}/tickets",
    tags=["Tickets"],
)
logger = logging.getLogger("app")


@router.patch(
    "/{ticket_id}/close",
    status_code=status.HTTP_200_OK,
)
async def close_ticket(
    ticket_id: UUID,
    project_id: UUID,
    organization_id: UUID,
    payload: TicketCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Close a ticket with optional closing notes.

    This endpoint closes a ticket, marking it as resolved or handled.
    Only users with 'close_tickets' permission can close tickets.
    The ticket must belong to the specified project and organization.

    Args:
        ticket_id (UUID): Unique identifier of the ticket to close.
        project_id (UUID): Unique identifier of the project containing the ticket.
        organization_id (UUID): Organization ID for access verification.
        payload (TicketCloseRequest): Optional closing notes:
            - closing_notes (Optional[str]): Notes explaining
            why the ticket was closed (max 1000 chars)
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Ticket closed successfully"
            - data (TicketResponse): Complete ticket details with updated status.

    Raises:
        HTTPException:
            - 400 Bad Request if ticket is already closed
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user lacks close_tickets permission or ticket
              belongs to different org/project
            - 404 Not Found if ticket doesn't exist
            - 500 Internal Server Error if operation fails
    """
    logger.info(f"Closing ticket_id={ticket_id} by user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        ticket_service = TicketService(db)
        ticket = await ticket_service.close_ticket(
            ticket_id=ticket_id,
            project_id=project_id,
            organization_id=organization_id,
            user_id=current_user.id,
            close_data=payload,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Ticket closed successfully",
            data=TicketResponse.model_validate(ticket),
        )

    except ValueError as e:
        error_message = str(e)
        logger.warning(f"Ticket closure failed: {error_message}")

        if "already closed" in error_message.lower():
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=error_message,
            )
        elif "permission" in error_message.lower():
            return error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                message=error_message,
            )
        else:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message=error_message,
            )

    except Exception:
        logger.exception(f"Error closing ticket_id={ticket_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to close ticket. Please try again.",
        )
