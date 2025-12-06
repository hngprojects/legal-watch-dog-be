"""
Ticket Routes
API endpoint for manual ticket creation.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.tickets.schemas import (
    TicketCreate,
    TicketResponse,
)
from app.api.modules.v1.tickets.service import TicketService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import (
    error_response,
    success_response,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/organizations/{organization_id}/projects/{project_id}/tickets",
    tags=["Tickets"],
)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TicketResponse)
async def create_manual_ticket(
    organization_id: UUID,
    project_id: UUID,
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new manual ticket.

    This endpoint allows users to manually create tickets for revisions or observations
    that require discussion or follow-up. Teams can escalate or discuss any issue,
    not just automated change events.

    **Requirements:**
    - User must be a member of the organization
    - User must have permission to create projects/tickets
    - Project must exist and belong to the organization

    **Request Body:**
    - **title** (required): Ticket title (1-255 characters)
    - **description** (optional): Detailed description
    - **content** (optional): JSON data about changes or observations
    - **priority** (required): Priority level (low, medium, high, critical)
    - **source_id** (optional): Link to a source if applicable
    - **data_revision_id** (optional): Link to a data revision if applicable
    - **assigned_to_user_id** (optional): User to assign the ticket to
    - **project_id** (required): Project to associate the ticket with

    **Returns:**
    - Created ticket with full details including related users
    """
    user_id = str(current_user.id)

    try:
        result = await db.execute(
            select(UserOrganization)
            .where(UserOrganization.user_id == current_user.id)
            .where(UserOrganization.organization_id == organization_id)
        )
        membership = result.scalars().first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not a member of this organization",
            )

        if data.project_id != project_id:
            logger.warning(
                f"Project ID mismatch: URL={project_id}, Body={data.project_id}, user_id={user_id}"
            )
            return error_response(
                message="Project ID in request body must match URL parameter",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        ticket_service = TicketService(db)
        ticket = await ticket_service.create_manual_ticket(
            data=data,
            organization_id=organization_id,
            user_id=current_user.id,
        )

        logger.info(f"Successfully created ticket {ticket.id} for user {current_user.id}")

        return success_response(
            data=ticket,
            message="Ticket created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    except ValueError as e:
        logger.warning(f"Validation error creating ticket: {str(e)}, user_id={user_id}")
        return error_response(
            message=str(e),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.exception(f"Error creating ticket: {str(e)}, user_id={user_id}")
        return error_response(
            message="An error occurred while creating the ticket",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
