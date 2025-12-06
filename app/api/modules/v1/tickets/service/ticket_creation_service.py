import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketPriority
from app.api.modules.v1.users.models.users_model import User

if TYPE_CHECKING:
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.service.diff_service import ChangeDetectionResult


class TicketService:
    """
    Service to handle creation of tickets automatically when
    a meaningful change is detected in a data revision.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.
        """
        self.db = db

    @staticmethod
    def map_risk_to_priority(risk_level: Optional[str]) -> TicketPriority:
        """
        Maps the risk level detected by AI to the ticket priority.

        Args:
            risk_level (Optional[str]): Risk level string ("LOW", "MEDIUM", "HIGH", "NONE").

        Returns:
            TicketPriority: The corresponding ticket priority.
        """
        risk_map = {
            "HIGH": TicketPriority.CRITICAL,
            "MEDIUM": TicketPriority.HIGH,
            "LOW": TicketPriority.MEDIUM,
        }
        risk_upper = risk_level.upper() if risk_level else "NONE"
        return risk_map.get(risk_upper, TicketPriority.MEDIUM)

    async def create_auto_ticket(
        self,
        revision: "DataRevision",
        source: "Source",
        jurisdiction: "Jurisdiction",
        project: "Project",
        change_result: "ChangeDetectionResult",
    ) -> Ticket:
        """
        Creates an automatic ticket for a data revision with a detected change.

        Args:
            revision (DataRevision): The revision object that triggered the ticket.
            source (Source): The source of the revision.
            jurisdiction (Jurisdiction): The jurisdiction the source belongs to.
            project (Project): The project the source belongs to.
            change_result (ChangeDetectionResult): The result from the DiffAIService.

        Returns:
            Ticket: The newly created ticket.
        """
        query = select(User).where(User.is_active.is_(True)).limit(1)
        result = await self.db.execute(query)
        any_active_user: Optional[User] = result.scalars().first()
        created_by_user_id = any_active_user.id if any_active_user else None

        title = change_result.change_summary or f"Change Detected in Source {revision.source_id}"

        description = (
            f"### Automatic Ticket Generated\n\n"
            f"**Source ID:** {revision.source_id}\n"
            f"**Revision ID:** {revision.id}\n"
            f"**Risk Level:** {change_result.risk_level}\n"
            f"**Confidence:** {revision.ai_confidence_score}\n\n"
            f"### Change Summary\n"
            f"{change_result.change_summary}\n\n"
            f"### AI Summary\n"
            f"{revision.ai_markdown_summary or revision.ai_summary}\n"
        )

        priority = self.map_risk_to_priority(change_result.risk_level)

        ticket = Ticket(
            title=title,
            description=description,
            status="open",
            priority=priority,
            is_manual=False,
            data_revision_id=revision.id,
            created_by_user_id=created_by_user_id,
            assigned_to_user_id=None,
            organization_id=jurisdiction.project.organization_id,
            project_id=project.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)

        return ticket            project_id: UUID of the project.
            organization_id: UUID of the organization.

        Returns:
            Ticket: The newly created ticket.
        """

        query = select(User).where(User.is_active.is_(True)).limit(1)


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
