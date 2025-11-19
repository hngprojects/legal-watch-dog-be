from typing import Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.api.modules.v1.tickets.models.ticket import Ticket
from app.api.modules.v1.projects.models.project import Project
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.tickets.schemas.ticket import TicketCreateRequest
from app.api.core.logger import setup_logging
import logging
import uuid

setup_logging()
logger = logging.getLogger("app")


async def create_ticket(
    db: AsyncSession,
    data: TicketCreateRequest,
    current_user: User,
) -> Ticket:
    """
    Create a new ticket in the database.

    Args:
        db: Database session
        data: Ticket creation request data
        current_user: Currently authenticated user

    Returns:
        Created Ticket object

    Raises:
        HTTPException: If project not found or doesn't belong to user's organization
        HTTPException: If assigned user not found or doesn't belong to same organization
    """
    logger.info(
        f"Creating ticket '{data.title}' for project {data.project_id} "
        f"by user {current_user.id}"
    )

    # Validate project exists and belongs to user's organization
    try:
        project_uuid = uuid.UUID(data.project_id)
    except ValueError:
        logger.warning(f"Invalid project_id format: {data.project_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID format",
        )

    project = await db.scalar(
        select(Project).where(
            Project.id == project_uuid,
            Project.organization_id == current_user.organization_id,
        )
    )

    if not project:
        logger.warning(
            f"Project {data.project_id} not found or doesn't belong to "
            f"organization {current_user.organization_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    # Validate assigned_to user if provided
    assigned_to_uuid: Optional[uuid.UUID] = None
    if data.assigned_to:
        try:
            assigned_to_uuid = uuid.UUID(data.assigned_to)
        except ValueError:
            logger.warning(f"Invalid assigned_to format: {data.assigned_to}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid assigned user ID format",
            )

        assigned_user = await db.scalar(
            select(User).where(
                User.id == assigned_to_uuid,
                User.organization_id == current_user.organization_id,
            )
        )

        if not assigned_user:
            logger.warning(
                f"Assigned user {data.assigned_to} not found or doesn't "
                f"belong to organization"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned user not found or access denied",
            )

    # Create the ticket
    ticket = Ticket(
        organization_id=current_user.organization_id,
        project_id=project_uuid,
        created_by=current_user.id,
        assigned_to=assigned_to_uuid,
        title=data.title,
        description=data.description,
        status=data.status or "open",
        priority=data.priority or "medium",
    )

    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    logger.info(f"Successfully created ticket {ticket.id} with title '{ticket.title}'")
    return ticket


async def get_ticket_by_id(
    db: AsyncSession, ticket_id: uuid.UUID, organization_id: uuid.UUID
) -> Optional[Ticket]:
    """
    Retrieve a ticket by ID, ensuring it belongs to the specified organization.

    Args:
        db: Database session
        ticket_id: UUID of the ticket
        organization_id: UUID of the organization

    Returns:
        Ticket object if found, None otherwise
    """
    return await db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id, Ticket.organization_id == organization_id
        )
    )
