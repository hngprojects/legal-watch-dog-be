import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketPriority
from app.api.modules.v1.users.models.users_model import User


class TicketService:
    """
    Service to handle creation of tickets automatically when
    a meaningful change is detected in a data revision.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize with the database session.
        """
        self.db = db

    async def create_auto_ticket(
        self,
        revision,
        change_result,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Ticket:
        """
        Creates a non-manual ticket based on detected change.

        Args:
            revision: The DataRevision object that triggered this ticket.
            change_result: Result from DiffAIService.
            project_id: UUID of the project.
            organization_id: UUID of the organization.

        Returns:
            Ticket: The newly created ticket.
        """

        query = (
            select(User)
            .where(
                User.organization_id == organization_id,
                User.is_active.is_(True),
                User.is_superuser.is_(True),
            )
            .limit(1)
        )

        result = await self.db.execute(query)
        admin_user: Optional[User] = result.scalars().first()

        created_by_user_id = admin_user.id if admin_user else None

        title = f"Change Detected in Source {revision.source_id}"
        description = (
            f"Automatic ticket created from data revision {revision.id}.\n\n"
            f"Summary of change:\n{change_result.change_summary}\n"
            f"Risk Level: {change_result.risk_level}"
        )

        ticket = Ticket(
            title=title,
            description=description,
            status="open",
            priority=TicketPriority.MEDIUM,
            is_manual=False,
            data_revision_id=revision.id,
            created_by_user_id=created_by_user_id,
            assigned_to_user_id=None,
            organization_id=organization_id,
            project_id=project_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)

        return ticket
