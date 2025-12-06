import json
import logging
import math
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import and_, or_, select

from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.utils.project_utils import (
    check_project_user_exists,
    get_project_by_id,
)
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.api.modules.v1.tickets.schemas.ticket_schema import TicketCreate

logger = logging.getLogger("app")


class TicketService:
    """Service class for ticket-related business logic operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.

        Args:
            db: Async database session for executing queries
        """
        self.db = db

    async def _verify_organization_membership(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> None:
        """
        Verify that a user is a member of an organization.

        Args:
            user_id: UUID of the user
            organization_id: UUID of the organization

        Raises:
            ValueError: If user is not a member of the organization
        """
        result = await self.db.execute(
            select(UserOrganization)
            .where(UserOrganization.user_id == user_id)
            .where(UserOrganization.organization_id == organization_id)
            .where(UserOrganization.is_active)
        )
        membership = result.scalars().first()
        if not membership:
            raise ValueError("User not a member of this organization")

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
            Created Ticket object with relationships loaded

        Raises:
            ValueError: If user lacks permission or project not found
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
                f"Creating ticket '{auto_title}'",
                extra={
                    "user_id": str(user_id),
                    "organization_id": str(organization_id),
                    "project_id": str(data.project_id),
                },
            )

            content_str = json.dumps(auto_content) if auto_content else None

            ticket = Ticket(
                title=auto_title,
                description=auto_description,
                content=content_str,
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
            await self.db.refresh(
                ticket,
                ["created_by_user", "assigned_by_user", "assigned_to_user"],
            )
            await self.db.commit()

            logger.info("Created ticket successfully", extra={"ticket_id": str(ticket.id)})

            return ticket

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating ticket: {str(e)}", exc_info=True)
            raise

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
    ) -> Dict[str, Any]:
        """
        List tickets with filtering and pagination.

        Args:
            organization_id: Organization UUID
            project_id: Project UUID
            user_id: User UUID requesting the list
            status: Optional status filter
            priority: Optional priority filter
            assigned_to_user_id: Optional assignee filter
            created_by_user_id: Optional creator filter
            q: Search query for title/description
            page: Page number (1-indexed)
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
            "Listing tickets",
            extra={
                "organization_id": str(organization_id),
                "project_id": str(project_id),
                "status": status.value if status else None,
                "priority": priority.value if priority else None,
                "page": page,
                "limit": limit,
            },
        )

        
        statement = (
            select(Ticket)
            .where(
                and_(
                    Ticket.organization_id == organization_id,
                    Ticket.project_id == project_id,
                )
            )
            .options(
                selectinload(Ticket.created_by_user),
                selectinload(Ticket.assigned_by_user),
                selectinload(Ticket.assigned_to_user),
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

        
        count_statement = select(func.count()).select_from(statement.subquery())
        total_result = await self.db.execute(count_statement)
        total = total_result.scalar() or 0

        
        statement = statement.order_by(desc(Ticket.created_at))

        
        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit)

        
        result = await self.db.execute(statement)
        tickets = result.scalars().all()

        
        total_pages = math.ceil(total / limit) if total > 0 else 0

       
        tickets_data = [self._build_ticket_response(ticket) for ticket in tickets]

        return {
            "data": tickets_data,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        }

    async def get_ticket_details(
        self,
        ticket_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get detailed ticket information with all relationships loaded.

        Args:
            ticket_id: Ticket UUID
            organization_id: Organization UUID for access control
            project_id: Project UUID for access control
            user_id: User UUID requesting the details

        Returns:
            Dictionary with complete ticket details

        Raises:
            ValueError: If ticket not found or user doesn't have access
        """
        
        is_project_member = await check_project_user_exists(self.db, project_id, user_id)
        if not is_project_member:
            raise ValueError("You must be a member of the project to view this ticket")

        
        statement = (
            select(Ticket)
            .where(
                and_(
                    Ticket.id == ticket_id,
                    Ticket.organization_id == organization_id,
                    Ticket.project_id == project_id,
                )
            )
            .options(
                selectinload(Ticket.created_by_user),
                selectinload(Ticket.assigned_by_user),
                selectinload(Ticket.assigned_to_user),
                selectinload(Ticket.source),
                selectinload(Ticket.data_revision),
                selectinload(Ticket.change_diff),
                selectinload(Ticket.external_participants).selectinload(
                    ExternalParticipant.invited_by_user
                ),
                selectinload(Ticket.invited_users),
            )
        )

        result = await self.db.execute(statement)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise ValueError(f"Ticket with id {ticket_id} not found")

        return self._build_ticket_detail_response(ticket)

    async def get_ticket_members(
        self,
        ticket_id: UUID,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get all members (users and external participants) involved in a ticket.

        Args:
            ticket_id: Ticket UUID
            organization_id: Organization UUID for access control
            project_id: Project UUID for access control
            user_id: User UUID requesting the data

        Returns:
            Dictionary containing ticket members

        Raises:
            ValueError: If ticket not found or user doesn't have access
        """
        
        is_project_member = await check_project_user_exists(self.db, project_id, user_id)
        if not is_project_member:
            raise ValueError("You must be a member of the project to view this ticket")

        
        statement = (
            select(Ticket)
            .where(
                and_(
                    Ticket.id == ticket_id,
                    Ticket.organization_id == organization_id,
                    Ticket.project_id == project_id,
                )
            )
            .options(
                selectinload(Ticket.created_by_user),
                selectinload(Ticket.assigned_by_user),
                selectinload(Ticket.assigned_to_user),
                selectinload(Ticket.external_participants).selectinload(
                    ExternalParticipant.invited_by_user
                ),
                selectinload(Ticket.invited_users),
            )
        )

        result = await self.db.execute(statement)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise ValueError(f"Ticket with id {ticket_id} not found")

       
        external_participants = []
        if ticket.external_participants:
            for participant in ticket.external_participants:
                external_participants.append(
                    {
                        "id": str(participant.id),
                        "email": participant.email,
                        "role": participant.role,
                        "invited_at": participant.invited_at.isoformat()
                        if participant.invited_at
                        else None,
                        "invited_by_user": self._build_user_detail(participant.invited_by_user),
                        "last_accessed_at": participant.last_accessed_at.isoformat()
                        if participant.last_accessed_at
                        else None,
                        "is_active": participant.is_active,
                        "expires_at": participant.expires_at.isoformat()
                        if participant.expires_at
                        else None,
                    }
                )

        
        invited_users = []
        if ticket.invited_users:
            for user in ticket.invited_users:
                invited_users.append(self._build_user_detail(user))

        
        unique_user_ids = set()
        if ticket.created_by_user_id:
            unique_user_ids.add(ticket.created_by_user_id)
        if ticket.assigned_by_user_id:
            unique_user_ids.add(ticket.assigned_by_user_id)
        if ticket.assigned_to_user_id:
            unique_user_ids.add(ticket.assigned_to_user_id)
        if ticket.invited_users:
            for user in ticket.invited_users:
                unique_user_ids.add(user.id)

        total_members = len(unique_user_ids) + len(external_participants)

        return {
            "ticket_id": str(ticket.id),
            "created_by_user": self._build_user_detail(ticket.created_by_user),
            "assigned_by_user": self._build_user_detail(ticket.assigned_by_user),
            "assigned_to_user": self._build_user_detail(ticket.assigned_to_user),
            "invited_users": invited_users,
            "external_participants": external_participants,
            "total_members": total_members,
        }

    async def list_organization_tickets(
        self,
        organization_id: UUID,
        user_id: UUID,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        project_id: Optional[UUID] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        List tickets across all projects in an organization.

        Args:
            organization_id: Organization UUID
            user_id: User UUID requesting the list
            status: Optional status filter
            priority: Optional priority filter
            project_id: Optional project filter
            page: Page number
            limit: Items per page

        Returns:
            Dictionary with tickets list and pagination metadata

        Raises:
            ValueError: If user is not a member of the organization
        """
        
        await self._verify_organization_membership(user_id, organization_id)

        logger.info(
            "Listing organization tickets",
            extra={
                "organization_id": str(organization_id),
                "status": status.value if status else None,
                "priority": priority.value if priority else None,
                "page": page,
                "limit": limit,
            },
        )

        
        statement = (
            select(Ticket)
            .where(Ticket.organization_id == organization_id)
            .options(
                selectinload(Ticket.created_by_user),
                selectinload(Ticket.assigned_by_user),
                selectinload(Ticket.assigned_to_user),
            )
        )

        
        if status:
            statement = statement.where(Ticket.status == status)

        if priority:
            statement = statement.where(Ticket.priority == priority)

        if project_id:
            statement = statement.where(Ticket.project_id == project_id)

        
        count_statement = select(func.count()).select_from(statement.subquery())
        total_result = await self.db.execute(count_statement)
        total = total_result.scalar() or 0

        
        statement = statement.order_by(desc(Ticket.created_at))

       
        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit)

       
        result = await self.db.execute(statement)
        tickets = result.scalars().all()

        
        total_pages = math.ceil(total / limit) if total > 0 else 0

       
        tickets_data = [self._build_ticket_response(ticket) for ticket in tickets]

        return {
            "data": tickets_data,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        }

    def _build_user_detail(self, user) -> Optional[Dict[str, Any]]:
        """
        Build user detail dictionary from User object.

        Args:
            user: User object or None

        Returns:
            Dictionary with user details or None
        """
        if not user:
            return None

        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
        }

    def _build_ticket_response(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Build ticket response dictionary.

        Args:
            ticket: Ticket object

        Returns:
            Dictionary with ticket data
        """
        
        content_dict = None
        if ticket.content:
            try:
                content_dict = json.loads(ticket.content)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in ticket {ticket.id} content")
                content_dict = None

        return {
            "id": str(ticket.id),
            "title": ticket.title,
            "description": ticket.description,
            "content": content_dict,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "is_manual": ticket.is_manual,
            "source_id": str(ticket.source_id) if ticket.source_id else None,
            "data_revision_id": str(ticket.data_revision_id) if ticket.data_revision_id else None,
            "change_diff_id": str(ticket.change_diff_id) if ticket.change_diff_id else None,
            "created_by_user_id": str(ticket.created_by_user_id)
            if ticket.created_by_user_id
            else None,
            "assigned_by_user_id": str(ticket.assigned_by_user_id)
            if ticket.assigned_by_user_id
            else None,
            "assigned_to_user_id": str(ticket.assigned_to_user_id)
            if ticket.assigned_to_user_id
            else None,
            "organization_id": str(ticket.organization_id),
            "project_id": str(ticket.project_id),
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            "created_by_user": self._build_user_detail(ticket.created_by_user),
            "assigned_by_user": self._build_user_detail(ticket.assigned_by_user),
            "assigned_to_user": self._build_user_detail(ticket.assigned_to_user),
        }

    def _build_ticket_detail_response(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Build detailed ticket response with all relationships.

        Args:
            ticket: Ticket object with loaded relationships

        Returns:
            Dictionary with complete ticket details
        """
        base_response = self._build_ticket_response(ticket)

       
        external_participants = []
        if ticket.external_participants:
            for participant in ticket.external_participants:
                external_participants.append(
                    {
                        "id": str(participant.id),
                        "email": participant.email,
                        "role": participant.role,
                        "invited_at": participant.invited_at.isoformat()
                        if participant.invited_at
                        else None,
                        "last_accessed_at": participant.last_accessed_at.isoformat()
                        if participant.last_accessed_at
                        else None,
                        "is_active": participant.is_active,
                        "expires_at": participant.expires_at.isoformat()
                        if participant.expires_at
                        else None,
                        "invited_by_user": self._build_user_detail(participant.invited_by_user),
                    }
                )

        
        invited_users = []
        if ticket.invited_users:
            for user in ticket.invited_users:
                invited_users.append(self._build_user_detail(user))

        base_response["external_participants"] = external_participants
        base_response["invited_users"] = invited_users

        return base_response