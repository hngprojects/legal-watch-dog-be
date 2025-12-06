"""
Ticket Routes
API endpoint for manual ticket creation.
"""

import logging

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
    prefix="/tickets",
    tags=["Tickets"],
)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TicketResponse)
async def create_manual_ticket(
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
    - User must be a member of the source's organization
    - Source must exist and contain organization_id, project_id, jurisdiction_id

    **Request Body:**
    - **source_id** (required): Source ID - derives organization, project, jurisdiction
    - **revision_id** (required): Data Revision ID - specific revision that triggered this ticket
    - **priority** (optional): Ticket priority - low, medium, high, or critical

    **Returns:**
    - Created ticket with full details
    """
    user_id = str(current_user.id)

    try:
        from app.api.modules.v1.scraping.models.source_model import Source

        source_result = await db.execute(select(Source).where(Source.id == data.source_id))
        source = source_result.scalar_one_or_none()

        if not source:
            return error_response(
                message="Source not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        organization_id = source.organization_id

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
