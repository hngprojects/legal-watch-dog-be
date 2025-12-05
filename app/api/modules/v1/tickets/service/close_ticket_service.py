"""
Ticket Services
Business logic for ticket operations with proper database integration
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketStatus
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import TicketCloseRequest
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class TicketService:
    """
    Service class for ticket-related business logic operations.

    This class encapsulates ticket operations including closing and
    other ticket state management.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    async def close_ticket(
        self,
        ticket_id: UUID,
        project_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        close_data: TicketCloseRequest,
    ) -> Ticket:
        """
        Close a ticket with provided data.

        Args:
            ticket_id: ID of the ticket to close
            project_id: ID of the project the ticket belongs to
            organization_id: ID of the organization
            user_id: ID of the user closing the ticket
            close_data: Closing request data with optional notes

        Returns:
            Updated Ticket object after closing

        Raises:
            ValueError: If permission denied, ticket not found, or already closed
            Exception: For database errors
        """
        # Check user permissions
        has_permission = await check_user_permission(
            self.db, user_id, organization_id, "close_tickets"
        )

        if not has_permission:
            raise ValueError("You do not have permission to close tickets")

        logger.info(f"Closing ticket_id={ticket_id} by user_id={user_id}")

        # Find the ticket
        statement = select(Ticket).where(Ticket.id == ticket_id)
        result = await self.db.execute(statement)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise ValueError("Ticket not found")

        # Verify ticket belongs to the correct project and organization
        if ticket.project_id != project_id:
            raise ValueError("Ticket does not belong to the specified project")

        if ticket.organization_id != organization_id:
            raise ValueError("Ticket does not belong to the specified organization")

        # Check if ticket is already closed
        if ticket.status.value == "closed":
            raise ValueError("Ticket is already closed")

        # Update ticket status and timestamps
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.now(timezone.utc)
        ticket.updated_at = datetime.now(timezone.utc)

        # Add closing notes if provided
        if close_data.closing_notes:
            # Store notes in description if it's currently empty, or append if it has content
            if not ticket.description:
                ticket.description = f"Closing notes: {close_data.closing_notes}"
            else:
                ticket.description += f"\n\nClosing notes: {close_data.closing_notes}"

        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)

        logger.info(f"Ticket closed successfully: ticket_id={ticket_id}, user_id={user_id}")

        return ticket
