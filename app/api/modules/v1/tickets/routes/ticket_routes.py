"""Ticket Management Routes"""

import logging
from fastapi import APIRouter, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.tickets.service.ticket_service import create_ticket
from app.api.modules.v1.tickets.schemas.ticket import (
    TicketCreateRequest,
    TicketResponse,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.core.dependencies.auth import get_current_user
from app.api.utils.response_payloads import success_response
from app.api.db.database import get_db

router = APIRouter(prefix="/tickets", tags=["Tickets"])

logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_ticket(
    payload: TicketCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new ticket.

    Creates a ticket with title, description, and assigned project.
    Tickets are automatically associated with the user's organization.

    Args:
        payload: Ticket creation request data
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Created ticket data

    Raises:
        404: Project not found or access denied
        400: Invalid project ID or assigned user ID format
    """
    logger.info(
        f"User {current_user.id} creating ticket '{payload.title}' "
        f"for project {payload.project_id}"
    )

    ticket = await create_ticket(db, payload, current_user)

    return success_response(
        message="Ticket created successfully",
        status_code=status.HTTP_201_CREATED,
        data={
            "id": str(ticket.id),
            "organization_id": str(ticket.organization_id),
            "project_id": str(ticket.project_id),
            "created_by": str(ticket.created_by),
            "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "priority": ticket.priority,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
        },
    )
