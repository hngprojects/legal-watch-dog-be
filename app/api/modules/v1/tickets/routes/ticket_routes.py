"""
Ticket Routes
API endpoint for manual ticket creation.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.tickets.models.ticket_model import TicketPriority, TicketStatus
from app.api.modules.v1.tickets.schemas import (
    TicketCreate,
    TicketResponse,
    UserDetail,
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

ticket_router = APIRouter(
    prefix="/organizations/{organization_id}/tickets",
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

        content_dict = json.loads(ticket.content) if ticket.content else None

        response_data = TicketResponse(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            content=content_dict,
            status=ticket.status,
            priority=ticket.priority,
            is_manual=ticket.is_manual,
            source_id=ticket.source_id,
            data_revision_id=ticket.data_revision_id,
            change_diff_id=ticket.change_diff_id,
            created_by_user_id=ticket.created_by_user_id,
            assigned_by_user_id=ticket.assigned_by_user_id,
            assigned_to_user_id=ticket.assigned_to_user_id,
            organization_id=ticket.organization_id,
            project_id=ticket.project_id,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            closed_at=ticket.closed_at,
            created_by_user=_build_user_detail(ticket.created_by_user)
            if ticket.created_by_user
            else None,
            assigned_by_user=_build_user_detail(ticket.assigned_by_user)
            if ticket.assigned_by_user
            else None,
            assigned_to_user=_build_user_detail(ticket.assigned_to_user)
            if ticket.assigned_to_user
            else None,
        )

        logger.info(f"Successfully created ticket {ticket.id} for user {current_user.id}")

        return success_response(
            data=response_data,
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


def _build_user_detail(user: User) -> UserDetail:
    """Helper function to build UserDetail from User object."""
    return UserDetail(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
    )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="List all tickets in a project",
    description="""
    List all tickets in a project with filtering and pagination.
    
    **Features:**
    - Filter by status, priority, assignee, and creator
    - Search by title and description
    - Paginate results with page/limit
    - Always sorted by created_at in descending order (newest first)
    - Returns ticket info with user details
    """,
)
async def list_tickets(
    organization_id: UUID,
    project_id: UUID,
    status_filter: TicketStatus | None = Query(
        None, alias="status", description="Filter by ticket status"
    ),
    priority: TicketPriority | None = Query(None, description="Filter by priority"),
    assigned_to_user_id: UUID | None = Query(None, description="Filter by assigned user"),
    created_by_user_id: UUID | None = Query(None, description="Filter by creator"),
    q: str | None = Query(None, max_length=255, description="Search in title/description"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all tickets in a project with filtering and pagination.

    Retrieves a paginated list of tickets for a specific project with optional
    filtering by status, priority, assignee, creator, and search query.
    Results are always sorted by creation date in descending order (newest first).

    Requirements:
    - User must be a member of the organization
    - User must be a member of the project

    Args:
        organization_id: UUID of the organization
        project_id: UUID of the project to retrieve tickets from
        status_filter: Optional filter by ticket status
        priority: Optional filter by ticket priority
        assigned_to_user_id: Optional filter by assigned user
        created_by_user_id: Optional filter by creator
        q: Optional search query for title/description
        page: Page number for pagination (default: 1)
        limit: Items per page (default: 20, max: 100)

    Returns:
        Success response containing:
        - data: List of ticket objects
        - total: Total count of tickets matching filters
        - page: Current page number
        - limit: Current limit value
        - total_pages: Total number of pages
    """
    try:
        ticket_service = TicketService(db)
        result = await ticket_service.list_tickets(
            organization_id=organization_id,
            project_id=project_id,
            user_id=current_user.id,
            status=status_filter,
            priority=priority,
            assigned_to_user_id=assigned_to_user_id,
            created_by_user_id=created_by_user_id,
            q=q,
            page=page,
            limit=limit,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Tickets retrieved successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to list tickets for project_id={project_id}, "
            f"user_id={current_user.id}: {str(e)}"
        )
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "not a member" in error_message.lower() or "permission" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            message=error_message,
            status_code=status_code,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch tickets for project_id={project_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            message="An error occurred while retrieving tickets",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@ticket_router.get(
    "/{ticket_id}",
    status_code=status.HTTP_200_OK,
    summary="Get detailed ticket information",
    description="""
    Get comprehensive details about a specific ticket.
    
    **Includes:**
    - Complete ticket information (title, description, content)
    - Status and priority
    - All user relationships (creator, assigner, assigned user)
    - Related source and data revision information
    - Timestamps (created, updated, closed)
    - List of external participants (if any)
    """,
)
async def get_ticket_details(
    organization_id: UUID,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific ticket.

    Retrieves comprehensive details for a single ticket including all related
    user information, source data, data revision information, and metadata.

    Requirements:
    - User must be a member of the organization
    - Valid ticket_id must exist in the database

    Args:
        organization_id: UUID of the organization
        ticket_id: UUID of the ticket to retrieve

    Returns:
        Success response containing complete ticket details including
        external participants
    """
    try:
        ticket_service = TicketService(db)
        ticket_details = await ticket_service.get_ticket_details(
            ticket_id=ticket_id,
            organization_id=organization_id,
            user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Ticket details retrieved successfully",
            data=ticket_details,
        )

    except ValueError as e:
        logger.warning(f"Failed to get ticket details for ticket_id={ticket_id}: {str(e)}")
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "not a member" in error_message.lower() or "access" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch ticket details for ticket_id={ticket_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An error occurred while retrieving ticket details",
        )


@ticket_router.get(
    "/{ticket_id}/members",
    status_code=status.HTTP_200_OK,
    summary="List all members involved in a ticket",
    description="""
    Get all users who have access to or are involved in a ticket.
    
    **Includes:**
    - **Core team members:**
      - Created by user (ticket creator)
      - Assigned by user (who assigned the ticket)
      - Assigned to user (current assignee)
    - **External participants:** External people invited for scoped collaboration
      - Each includes invitation timestamp and access status
    - **Total member count:** Unique count of all involved users
    """,
)
async def get_ticket_members(
    organization_id: UUID,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all members (users and external participants) involved in a ticket.

    Retrieves a comprehensive list of all people who have access to or are
    involved with a specific ticket, including core team members and invited
    external participants.

    Requirements:
    - User must be a member of the organization
    - Valid ticket_id must exist in the database

    Args:
        organization_id: UUID of the organization
        ticket_id: UUID of the ticket to retrieve members for

    Returns:
        Success response containing:
        - ticket_id: UUID of the ticket
        - created_by_user: User who created the ticket
        - assigned_by_user: User who assigned the ticket
        - assigned_to_user: User currently assigned to the ticket
        - external_participants: List of external people invited
        - total_members: Count of all involved people
    """
    try:
        ticket_service = TicketService(db)
        members = await ticket_service.get_ticket_members(
            ticket_id=ticket_id,
            organization_id=organization_id,
            user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Ticket members retrieved successfully",
            data=members,
        )

    except ValueError as e:
        logger.warning(f"Failed to get ticket members for ticket_id={ticket_id}: {str(e)}")
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "not a member" in error_message.lower() or "access" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            status_code=status_code,
            message=error_message,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch ticket members for ticket_id={ticket_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An error occurred while retrieving ticket members",
        )


@ticket_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="List all tickets in an organization",
    description="""
    List all tickets across all projects in an organization.
    
    **Features:**
    - Filter by status, priority, and project
    - Paginate results with page/limit
    - Always sorted by created_at in descending order (newest first)
    - Useful for organization-level dashboards and reporting
    """,
)
async def list_organization_tickets(
    organization_id: UUID,
    status_filter: TicketStatus | None = Query(
        None, alias="status", description="Filter by ticket status"
    ),
    priority: TicketPriority | None = Query(None, description="Filter by priority"),
    project_id_filter: UUID | None = Query(
        None, alias="project_id", description="Filter by project"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all tickets in an organization across all projects.

    Retrieves a paginated list of tickets across all projects within a specific
    organization. Supports filtering by status, priority, and individual projects.
    Results are always sorted by creation date in descending order (newest first).

    This endpoint is useful for organization-level dashboards, reporting, and
    getting a bird's-eye view of all ticket activity across multiple projects.

    Requirements:
    - User must be a member of the organization

    Args:
        organization_id: UUID of the organization to retrieve tickets from
        status_filter: Optional filter by ticket status
        priority: Optional filter by ticket priority
        project_id_filter: Optional filter to show tickets from a specific project only
        page: Page number for pagination (default: 1)
        limit: Items per page (default: 20, max: 100)

    Returns:
        Success response containing:
        - data: List of ticket objects from all projects
        - total: Total count of tickets matching filters
        - page: Current page number
        - limit: Current limit value
        - total_pages: Total number of pages
    """
    try:
        ticket_service = TicketService(db)
        result = await ticket_service.list_tickets_by_organization(
            organization_id=organization_id,
            user_id=current_user.id,
            status=status_filter,
            priority=priority,
            project_id=project_id_filter,
            page=page,
            limit=limit,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Organization tickets retrieved successfully",
            data=result,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to list organization tickets for organization_id={organization_id}: {str(e)}"
        )
        error_message = str(e)

        if "not found" in error_message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "not a member" in error_message.lower() or "access" in error_message.lower():
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(
            message=error_message,
            status_code=status_code,
        )

    except Exception as e:
        logger.error(
            f"Failed to fetch tickets for organization_id={organization_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An error occurred while retrieving organization tickets",
        )
