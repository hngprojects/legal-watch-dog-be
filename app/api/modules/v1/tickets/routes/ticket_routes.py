import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.tickets.models.ticket_model import TicketPriority, TicketStatus
from app.api.modules.v1.tickets.schemas.ticket_schema import (
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
)
from app.api.modules.v1.tickets.service.ticket_service import TicketService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger("app")


router = APIRouter(
    prefix="/organizations/{organization_id}/projects/{project_id}/tickets",
    tags=["Tickets"],
    dependencies=[Depends(require_billing_access)],
)


org_router = APIRouter(
    prefix="/organizations/{organization_id}/tickets",
    tags=["Tickets"],
    dependencies=[Depends(require_billing_access)],
)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=TicketResponse,
    summary="Create a new manual ticket",
)
async def create_manual_ticket(
    organization_id: UUID,
    project_id: UUID,
    data: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new manual ticket.

    This endpoint allows users to manually create tickets for revisions or observations
    that require discussion or follow-up. Teams can escalate or discuss any issue,
    not just automated change events.

    Requirements:
        - User must be authenticated
        - User must be a member of the organization
        - User must be a member of the project
        - Project must exist and belong to the organization

    Args:
        organization_id: UUID of the organization
        project_id: UUID of the project
        data: Ticket creation data
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        TicketResponse with created ticket details
    """
    try:
        if data.project_id != project_id:
            logger.warning(
                "Project ID mismatch in create_manual_ticket",
                extra={
                    "url_project_id": str(project_id),
                    "body_project_id": str(data.project_id),
                    "user_id": str(current_user.id),
                },
            )
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Project ID in request body must match URL parameter",
            )

        ticket_service = TicketService(db)
        ticket = await ticket_service.create_manual_ticket(
            data=data,
            organization_id=organization_id,
            user_id=current_user.id,
        )

        logger.info(
            "Ticket created successfully",
            extra={
                "ticket_id": str(ticket.id),
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
                "project_id": str(project_id),
            },
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Ticket created successfully",
            data=ticket_service._build_ticket_response(ticket),
        )

    except ValueError as e:
        logger.warning(
            f"Validation error in create_manual_ticket: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
                "project_id": str(project_id),
            },
        )
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error creating ticket: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
                "project_id": str(project_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="An error occurred while creating the ticket. Please try again.",
        )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=TicketListResponse,
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
async def list_project_tickets(
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all tickets in a project with filtering and pagination.

    Retrieves a paginated list of tickets for a specific project with optional
    filtering by status, priority, assignee, creator, and search query.
    Results are always sorted by creation date in descending order (newest first).

    Requirements:
        - User must be authenticated
        - User must be a member of the organization
        - User must be a member of the project

    Args:
        organization_id: UUID of the organization
        project_id: UUID of the project
        status_filter: Optional filter by ticket status
        priority: Optional filter by ticket priority
        assigned_to_user_id: Optional filter by assigned user
        created_by_user_id: Optional filter by creator
        q: Optional search query for title/description
        page: Page number for pagination (default: 1)
        limit: Items per page (default: 20, max: 100)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        TicketListResponse containing paginated tickets and metadata
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
            f"Failed to list tickets: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
                "project_id": str(project_id),
            },
        )
        error_msg = str(e).lower()
        if "not a member" in error_msg:
            status_code = status.HTTP_403_FORBIDDEN
        elif "not found" in error_msg:
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(status_code=status_code, message=str(e))

    except Exception as e:
        logger.error(
            f"Error listing tickets: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
                "project_id": str(project_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="An error occurred while retrieving tickets. Please try again.",
        )


@router.get(
    "/{ticket_id}",
    status_code=status.HTTP_200_OK,
    response_model=TicketDetailResponse,
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
async def get_ticket_by_id(
    organization_id: UUID,
    project_id: UUID,
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a specific ticket.

    Retrieves comprehensive details for a single ticket including all related
    user information, source data, data revision information, and external participants.

    Requirements:
        - User must be authenticated
        - User must be a member of the organization
        - User must be a member of the project
        - Ticket must exist in the specified project

    Args:
        organization_id: UUID of the organization
        project_id: UUID of the project
        ticket_id: UUID of the ticket to retrieve
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        TicketDetailResponse with complete ticket details
    """
    try:
        ticket_service = TicketService(db)
        ticket_details = await ticket_service.get_ticket_details(
            ticket_id=ticket_id,
            organization_id=organization_id,
            project_id=project_id,
            user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Ticket details retrieved successfully",
            data=ticket_details,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to get ticket details: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
                "organization_id": str(organization_id),
                "project_id": str(project_id),
            },
        )
        error_msg = str(e).lower()
        if "not a member" in error_msg or "access" in error_msg:
            status_code = status.HTTP_403_FORBIDDEN
        elif "not found" in error_msg:
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(status_code=status_code, message=str(e))

    except Exception as e:
        logger.error(
            f"Error getting ticket details: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="An error occurred while retrieving ticket details. Please try again.",
        )


@router.get(
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
    project_id: UUID,
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all members (users and external participants) involved in a ticket.

    Retrieves a comprehensive list of all people who have access to or are
    involved with a specific ticket, including core team members and invited
    external participants.

    Requirements:
        - User must be authenticated
        - User must be a member of the organization
        - User must be a member of the project
        - Ticket must exist in the specified project

    Args:
        organization_id: UUID of the organization
        project_id: UUID of the project
        ticket_id: UUID of the ticket
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        Dictionary containing all ticket members and participant details
    """
    try:
        ticket_service = TicketService(db)
        members = await ticket_service.get_ticket_members(
            ticket_id=ticket_id,
            organization_id=organization_id,
            project_id=project_id,
            user_id=current_user.id,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Ticket members retrieved successfully",
            data=members,
        )

    except ValueError as e:
        logger.warning(
            f"Failed to get ticket members: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        error_msg = str(e).lower()
        if "not a member" in error_msg or "access" in error_msg:
            status_code = status.HTTP_403_FORBIDDEN
        elif "not found" in error_msg:
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(status_code=status_code, message=str(e))

    except Exception as e:
        logger.error(
            f"Error getting ticket members: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "ticket_id": str(ticket_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="An error occurred while retrieving ticket members. Please try again.",
        )


@org_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=TicketListResponse,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all tickets in an organization across all projects.

    Retrieves a paginated list of tickets across all projects within a specific
    organization. Supports filtering by status, priority, and individual projects.
    Results are always sorted by creation date in descending order (newest first).

    This endpoint is useful for organization-level dashboards, reporting, and
    getting a bird's-eye view of all ticket activity across multiple projects.

    Requirements:
        - User must be authenticated
        - User must be a member of the organization

    Args:
        organization_id: UUID of the organization
        status_filter: Optional filter by ticket status
        priority: Optional filter by ticket priority
        project_id_filter: Optional filter for specific project
        page: Page number for pagination (default: 1)
        limit: Items per page (default: 20, max: 100)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        TicketListResponse containing paginated tickets across all projects
    """
    try:
        ticket_service = TicketService(db)
        result = await ticket_service.list_organization_tickets(
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
            f"Failed to list organization tickets: {str(e)}",
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
            },
        )
        error_msg = str(e).lower()
        if "not a member" in error_msg or "access" in error_msg:
            status_code = status.HTTP_403_FORBIDDEN
        elif "not found" in error_msg:
            status_code = status.HTTP_404_NOT_FOUND
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        return error_response(status_code=status_code, message=str(e))

    except Exception as e:
        logger.error(
            f"Error listing organization tickets: {str(e)}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(organization_id),
            },
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message="An error occurred while retrieving organization tickets. Please try again.",
        )