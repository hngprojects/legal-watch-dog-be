"""
Ticket Services
Business logic for ticket operations with proper database integration.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import and_, or_, select

from app.api.modules.v1.projects.utils.project_utils import (
    check_project_user_exists,
    get_project_by_id,
)
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.tickets.models.ticket_model import (
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.api.modules.v1.tickets.schemas.ticket_schema import TicketCreate

logger = logging.getLogger("app")


class TicketService:
    """
    Service class for ticket-related business logic operations.

    This class encapsulates all ticket operations including creation,
    retrieval, updates, assignment, and user invitation.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    def _infer_priority_from_confidence(self, confidence_score: Optional[float]) -> TicketPriority:
        """
        Infer ticket priority from AI confidence score.

        Priority mapping:
        - 0.85 - 1.0  → CRITICAL (very high confidence in significant change)
        - 0.6 - 0.85  → HIGH (high confidence)
        - 0.3 - 0.6   → MEDIUM (moderate confidence)
        - 0.0 - 0.3   → LOW (low confidence)
        - None        → MEDIUM (default fallback)

        Args:
            confidence_score: AI confidence score (0.0 to 1.0)

        Returns:
            TicketPriority enum value
        """
        if confidence_score is None:
            return TicketPriority.MEDIUM

        if confidence_score >= 0.85:
            return TicketPriority.CRITICAL
        elif confidence_score >= 0.6:
            return TicketPriority.HIGH
        elif confidence_score >= 0.3:
            return TicketPriority.MEDIUM
        else:
            return TicketPriority.LOW

    async def create_manual_ticket(
        self,
        data: TicketCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> Ticket:
        """
        Create a new manual ticket from source and revision data.

        Args:
            data: Ticket creation data (source_id, revision_id, priority)
            organization_id: Organization UUID
            user_id: User UUID creating the ticket

        Returns:
            Created Ticket object with auto-populated title, description, and content

        Raises:
            ValueError: If source, revision not found or user lacks permission
        """
        try:
            from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
            from app.api.modules.v1.scraping.models.source_model import Source

            source_query = select(Source).where(Source.id == data.source_id)
            source_result = await self.db.execute(source_query)
            source = source_result.scalar_one_or_none()

            if not source:
                raise ValueError("Source not found")

            project_id = source.project_id

            project = await get_project_by_id(self.db, project_id, organization_id)
            if not project:
                raise ValueError("Project not found or does not belong to this organization")

            is_project_member = await check_project_user_exists(self.db, project_id, user_id)
            if not is_project_member:
                raise ValueError("You must be a member of the project to create tickets")

            revision_query = select(DataRevision).where(DataRevision.id == data.revision_id)
            revision_result = await self.db.execute(revision_query)
            revision = revision_result.scalar_one_or_none()

            if not revision:
                raise ValueError("Data revision not found")

            if revision.source_id != source.id:
                raise ValueError("Revision does not belong to the specified source")

            jurisdiction_query = select(Jurisdiction).where(
                Jurisdiction.id == source.jurisdiction_id
            )
            jurisdiction_result = await self.db.execute(jurisdiction_query)
            jurisdiction = jurisdiction_result.scalar_one_or_none()

            jurisdiction_name = jurisdiction.name if jurisdiction else "Unknown"
            auto_title = f"[{jurisdiction_name}] {source.name} - Change Detected"

            auto_description = revision.ai_summary or "No summary available"

            auto_content = {
                "revision_summary": revision.ai_summary,
                "source_name": source.name,
                "source_url": source.url,
                "jurisdiction": jurisdiction_name,
                "scraped_at": revision.scraped_at.isoformat() if revision.scraped_at else None,
                "content_hash": revision.content_hash,
            }

            ticket_priority = data.priority
            confidence_for_priority = None
            change_diff = None

            if revision.change_diffs:
                change_diff_query = (
                    select(ChangeDiff).where(ChangeDiff.new_revision_id == revision.id).limit(1)
                )
                change_diff_result = await self.db.execute(change_diff_query)
                change_diff = change_diff_result.scalar_one_or_none()

                if change_diff:
                    auto_content["diff_patch"] = change_diff.diff_patch
                    auto_content["ai_confidence"] = change_diff.ai_confidence
                    auto_content["change_diff_id"] = str(change_diff.diff_id)
                    confidence_for_priority = change_diff.ai_confidence

            if ticket_priority is None:
                confidence_score = confidence_for_priority or revision.ai_confidence_score
                ticket_priority = self._infer_priority_from_confidence(confidence_score)
                auto_content["priority_inferred_from_ai"] = True
                auto_content["ai_confidence_used"] = confidence_score
                logger.info(
                    f"Priority inferred as {ticket_priority.value} "
                    f"from AI confidence: {confidence_score}"
                )
            else:
                auto_content["priority_inferred_from_ai"] = False

            logger.info(
                f"Creating ticket '{auto_title}' for user_id={user_id}, "
                f"organization_id={organization_id}, project_id={project_id}"
            )

            ticket = Ticket(
                title=auto_title,
                description=auto_description,
                content=auto_content,
                priority=ticket_priority,
                status=TicketStatus.OPEN,
                is_manual=True,
                source_id=source.id,
                data_revision_id=revision.id,
                change_diff_id=change_diff.id if change_diff else None,
                created_by_user_id=user_id,
                assigned_to_user_id=None,
                assigned_by_user_id=None,
                organization_id=organization_id,
                project_id=project_id,
            )

            self.db.add(ticket)
            await self.db.flush()
            await self.db.refresh(ticket)
            await self.db.commit()

            logger.info(f"Created ticket with id={ticket.id}")

            return ticket

        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error creating ticket: {str(e)}")
            raise

    async def get_ticket_by_id(
        self,
        ticket_id: UUID,
        organization_id: UUID,
    ) -> Optional[Ticket]:
        """
        Get a ticket by ID with all relationships loaded.

        Args:
            ticket_id: Ticket UUID
            organization_id: Organization UUID for access control

        Returns:
            Ticket object or None if not found
        """
        statement = (
            select(Ticket)
            .where(
                and_(
                    Ticket.id == ticket_id,
                    Ticket.organization_id == organization_id,
                )
            )
            .options(
                selectinload(Ticket.created_by_user),
                selectinload(Ticket.assigned_by_user),
                selectinload(Ticket.assigned_to_user),
                selectinload(Ticket.invited_users),
            )
        )

        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def list_tickets(
        self,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to_user_id: Optional[UUID] = None,
        created_by_user_id: Optional[UUID] = None,
        q: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        List tickets with filtering and pagination.

        Args:
            organization_id: Organization UUID
            project_id: Project UUID (required)
            user_id: User UUID requesting the list
            status: Optional status filter (enum)
            priority: Optional priority filter (enum)
            assigned_to_user_id: Optional assignee filter
            created_by_user_id: Optional creator filter
            q: Search query for title/description
            page: Page number
            limit: Items per page

        Returns:
            Dictionary with tickets list and pagination metadata

        Raises:
            ValueError: If project not found or user not a member
        """
        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            raise ValueError("Project not found or does not belong to this organization")

        is_project_member = await check_project_user_exists(self.db, project_id, user_id)
        if not is_project_member:
            raise ValueError("You must be a member of the project to view tickets")

        logger.info(
            f"Listing tickets for organization_id={organization_id}, "
            f"project_id={project_id}, status={status}, priority={priority}, "
            f"page={page}, limit={limit}"
        )

        statement = select(Ticket).where(
            and_(
                Ticket.organization_id == organization_id,
                Ticket.project_id == project_id,
            )
        )

        if status:
            statement = statement.where(Ticket.status == status)

        if priority:
            statement = statement.where(Ticket.priority == priority)

        if assigned_to_user_id:
            statement = statement.where(Ticket.assigned_to_user_id == assigned_to_user_id)

        if created_by_user_id:
            statement = statement.where(Ticket.created_by_user_id == created_by_user_id)

        if q:
            search_filter = or_(
                Ticket.title.ilike(f"%{q}%"),
                Ticket.description.ilike(f"%{q}%"),
            )
            statement = statement.where(search_filter)
