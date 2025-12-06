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

    async def create_manual_ticket(
        self,
        data: TicketCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> Ticket:
        """
        Create a new manual ticket.

        Args:
            data: Ticket creation data
            organization_id: Organization UUID
            user_id: User UUID creating the ticket

        Returns:
            Created Ticket object

        Raises:
            ValueError: If user doesn't have permission to create tickets or project not found
        """
        try:
            project = await get_project_by_id(self.db, data.project_id, organization_id)
            if not project:
                raise ValueError("Project not found or does not belong to this organization")

            is_project_member = await check_project_user_exists(self.db, data.project_id, user_id)
            if not is_project_member:
                raise ValueError("You must be a member of the project to create tickets")

            change_diff_data = None
            auto_title = data.title
            auto_description = data.description
            auto_content = data.content
            source_id = data.source_id
            revision_id = data.data_revision_id

            if data.change_diff_id:
                logger.info(f"Fetching ChangeDiff {data.change_diff_id} for auto-population")

                change_diff_query = select(ChangeDiff).where(
                    ChangeDiff.diff_id == data.change_diff_id
                )
                change_diff_result = await self.db.execute(change_diff_query)
                change_diff = change_diff_result.scalar_one_or_none()

                if not change_diff:
                    raise ValueError("ChangeDiff not found")

                revision_query = select(DataRevision).where(
                    DataRevision.id == change_diff.new_revision_id
                )
                revision_result = await self.db.execute(revision_query)
                new_revision = revision_result.scalar_one_or_none()

                if not new_revision:
                    raise ValueError("Data revision not found")

                from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
                from app.api.modules.v1.scraping.models.source_model import Source

                source_query = (
                    select(Source)
                    .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
                    .where(Source.id == new_revision.source_id)
                    .where(Jurisdiction.project_id == data.project_id)
                )
                source_result = await self.db.execute(source_query)
                source = source_result.scalar_one_or_none()

                if not source:
                    raise ValueError(
                        "ChangeDiff does not belong to this project or source not found"
                    )

                change_diff_data = change_diff.diff_patch or {}
                source_id = new_revision.source_id
                revision_id = change_diff.new_revision_id

                if not data.title or data.title.strip() == "":
                    auto_title = (
                        f"Change detected in {source.name}" if source else "Change detected"
                    )

                if not data.description and new_revision.ai_summary:
                    auto_description = new_revision.ai_summary

                if not data.content:
                    auto_content = {
                        "change_summary": new_revision.ai_summary,
                        "diff_patch": change_diff_data,
                        "confidence": change_diff.ai_confidence,
                        "source_name": source.name if source else None,
                    }
                else:
                    auto_content = {
                        **data.content,
                        "change_summary": new_revision.ai_summary,
                        "diff_patch": change_diff_data,
                        "confidence": change_diff.ai_confidence,
                    }

            logger.info(
                f"Creating ticket '{auto_title}' for user_id={user_id}, "
                f"organization_id={organization_id}, project_id={data.project_id}"
            )

            ticket = Ticket(
                title=auto_title,
                description=auto_description,
                content=auto_content,
                priority=data.priority,
                status=TicketStatus.OPEN,
                is_manual=True,
                source_id=source_id,
                data_revision_id=revision_id,
                change_diff_id=data.change_diff_id,
                created_by_user_id=user_id,
                assigned_to_user_id=data.assigned_to_user_id,
                assigned_by_user_id=user_id if data.assigned_to_user_id else None,
                organization_id=organization_id,
                project_id=data.project_id,
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
                selectinload(Ticket.external_participants),
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
