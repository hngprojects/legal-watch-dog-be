"""
Service for automatic ticket creation from DataRevisions.
Located at: app/api/modules/v1/tickets/service/ticket_creation_service.py
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketPriority, TicketStatus
from app.api.modules.v1.users.models.users_model import User


class TicketCreationService:
    """
    Handles automatic ticket creation when changes are detected in scraping.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize with database session.

        Args:
            db_session: Async database session
        """
        self.db = db_session

    async def _find_any_project_user(self, project_id: uuid.UUID) -> Optional[User]:
        """
        Find ANY user in the project to be the ticket 'creator'.

        Args:
            project_id: UUID of the project

        Returns:
            User object or None if no user found
        """
        try:
            query = (
                select(User)
                .join(ProjectUser, ProjectUser.user_id == User.id)
                .where(ProjectUser.project_id == project_id)
                .limit(1)
            )

            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            return user
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error finding project user for project {project_id}: {e}")
            return None

    def _map_risk_to_priority(self, risk_level: str) -> TicketPriority:
        """
        Map risk level from DiffAIService to ticket priority.

        Args:
            risk_level: "LOW", "MEDIUM", "HIGH", or "NONE"

        Returns:
            Corresponding TicketPriority
        """
        if not risk_level or risk_level == "NONE":
            return TicketPriority.MEDIUM

        risk_upper = risk_level.upper()

        if risk_upper == "HIGH":
            return TicketPriority.CRITICAL
        elif risk_upper == "MEDIUM":
            return TicketPriority.HIGH
        elif risk_upper == "LOW":
            return TicketPriority.MEDIUM
        else:
            return TicketPriority.MEDIUM

    async def create_ticket_from_revision(
        self, revision, source, jurisdiction, project, change_summary: str, risk_level: str
    ) -> Ticket:
        """
        Create a ticket automatically when change is detected.

        Args:
            revision: DataRevision object
            source: Source object
            jurisdiction: Jurisdiction object
            project: Project object
            change_summary: Summary of changes from DiffAIService
            risk_level: Risk level from DiffAIService

        Returns:
            Created Ticket object

        Raises:
            ValueError: If no user found for created_by_user_id
        """

        project_user = await self._find_any_project_user(project.id)

        if not project_user:
            raise ValueError(
                f"No users found in project {project.id}. "
                f"Ticket creation requires created_by_user_id (non-nullable field)."
            )

        ticket_priority = self._map_risk_to_priority(risk_level)

        # 3. Build title (truncate if needed)
        title_max_length = 255
        base_title = f"Change Detected in {source.name}"

        if change_summary and change_summary != "No material changes detected":
            # Add first 50 chars of summary
            short_summary = change_summary[:50]
            title = f"{base_title}: {short_summary}"
            if len(title) > title_max_length:
                title = title[:title_max_length]
        else:
            title = base_title[:title_max_length]

        # 4. Build description
        description = f"""## 🚨 Automatically Generated Ticket

### 📋 Change Summary
{change_summary}

### ⚠️ Risk Assessment
**Detected Risk Level:** {risk_level}
**Ticket Priority:** {ticket_priority.value.upper()}

### 📍 Source Information
**Source:** {source.name}
**Jurisdiction:** {jurisdiction.name}
**Project:** {project.title}

### 🔗 Linked Data
**Data Revision ID:** {revision.id}
**Scraped At:** {revision.scraped_at.strftime("%Y-%m-%d %H:%M:%S UTC") 
                    if revision.scraped_at else "N/A"}

### 🤖 AI Analysis Summary
{revision.ai_summary or "No AI summary available"}

---
*This ticket was automatically generated when 
the monitoring system detected a change in the source.*
"""

        # 5. Create ticket
        ticket = Ticket(
            title=title,
            description=description,
            status=TicketStatus.OPEN,
            priority=ticket_priority,
            is_manual=False,  # Auto-generated
            data_revision_id=revision.id,
            created_by_user_id=project_user.id,
            assigned_to_user_id=None,
            organization_id=project.org_id,  # Use project.org_id
            project_id=project.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # 6. Save
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)

        return ticket
