import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.tickets.models.ticket_external_access_model import (
    TicketExternalAccess,
)
from app.api.modules.v1.tickets.models.ticket_model import Ticket
from app.api.modules.v1.tickets.schemas.ticket_external_access_schema import (
    ExternalAccessResponse,
    ExternalTicketDetailResponse,
)
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


class TicketExternalAccessService:
    """Service for handling external ticket access operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the service with a database session.

        Args:
            db: Async database session
        """
        self.db = db

    def _generate_secure_token(self) -> str:
        """
        Generate a secure random token for external access.

        Returns:
            str: Secure token prefixed with 'ext_'
        """
        random_token = secrets.token_urlsafe(48)
        return f"ext_{random_token}"

    async def create_external_access(
        self,
        ticket_id: UUID,
        created_by_user_id: UUID,
        email: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> ExternalAccessResponse:
        """
        Create a new external access token for a ticket.

        Args:
            ticket_id: UUID of the ticket to grant access to
            created_by_user_id: UUID of the user creating the access
            email: Optional email address of external user
            expires_in_days: Optional number of days until expiration

        Returns:
            ExternalAccessResponse with access details and URL

        Raises:
            ValueError: If ticket not found or user lacks permission
        """

        ticket_stmt = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.organization),
                selectinload(Ticket.project),
            )
        )
        result = await self.db.execute(ticket_stmt)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise ValueError("Ticket not found")

        user_stmt = select(User).where(User.id == created_by_user_id)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        token = self._generate_secure_token()

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        external_access = TicketExternalAccess(
            ticket_id=ticket_id,
            token=token,
            email=email,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(external_access)
        await self.db.commit()
        await self.db.refresh(external_access)

        logger.info(
            f"Created external access for ticket {ticket_id}",
            extra={
                "ticket_id": str(ticket_id),
                "access_id": str(external_access.id),
                "email": email,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )

        if email:
            await self._send_external_access_email(
                external_access=external_access,
                ticket=ticket,
                invited_by_user=user,
            )

        access_url = f"{settings.FRONTEND_URL}/external/tickets/{token}"

        return ExternalAccessResponse(
            id=str(external_access.id),
            ticket_id=str(external_access.ticket_id),
            token=external_access.token,
            email=external_access.email,
            expires_at=external_access.expires_at,
            is_active=external_access.is_active,
            access_count=external_access.access_count,
            created_at=external_access.created_at,
            access_url=access_url,
        )

    async def get_ticket_by_token(
        self,
        token: str,
    ) -> ExternalTicketDetailResponse:
        """
        Retrieve ticket details using an external access token.

        Args:
            token: External access token

        Returns:
            ExternalTicketDetailResponse with limited ticket data

        Raises:
            ValueError: If token invalid, expired, or revoked
        """

        stmt = (
            select(TicketExternalAccess)
            .where(TicketExternalAccess.token == token)
            .options(
                selectinload(TicketExternalAccess.ticket).selectinload(Ticket.organization),
                selectinload(TicketExternalAccess.ticket).selectinload(Ticket.project),
            )
        )
        result = await self.db.execute(stmt)
        external_access = result.scalar_one_or_none()

        if not external_access:
            logger.warning(f"Invalid external access token attempted: {token[:20]}...")
            raise ValueError("Invalid access token")

        if not external_access.is_active:
            logger.warning(
                "Revoked external access attempted",
                extra={"access_id": str(external_access.id)},
            )
            raise ValueError("This access link has been revoked")

        if external_access.expires_at:
            if datetime.now(timezone.utc) > external_access.expires_at:
                logger.warning(
                    "Expired external access attempted",
                    extra={"access_id": str(external_access.id)},
                )
                raise ValueError("This access link has expired")

        external_access.access_count += 1
        external_access.last_accessed_at = datetime.now(timezone.utc)
        await self.db.commit()

        logger.info(
            f"External access used for ticket {external_access.ticket_id}",
            extra={
                "access_id": str(external_access.id),
                "ticket_id": str(external_access.ticket_id),
                "access_count": external_access.access_count,
            },
        )

        ticket = external_access.ticket

        return ExternalTicketDetailResponse(
            id=str(ticket.id),
            title=ticket.title,
            description=ticket.description,
            content=ticket.content,
            status=ticket.status.value,
            priority=ticket.priority.value,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            organization_name=ticket.organization.name if ticket.organization else "Unknown",
            project_name=ticket.project.title if ticket.project else "Unknown",
        )

    async def revoke_external_access(
        self,
        access_id: UUID,
        current_user_id: UUID,
    ) -> bool:
        """
        Revoke an external access token.

        Args:
            access_id: UUID of the external access to revoke
            current_user_id: UUID of user performing revocation

        Returns:
            bool: True if successfully revoked

        Raises:
            ValueError: If access not found or user lacks permission
        """
        stmt = (
            select(TicketExternalAccess)
            .where(TicketExternalAccess.id == access_id)
            .options(selectinload(TicketExternalAccess.ticket).selectinload(Ticket.organization))
        )
        result = await self.db.execute(stmt)
        external_access = result.scalar_one_or_none()

        if not external_access:
            raise ValueError("External access not found")

        external_access.is_active = False
        external_access.revoked_at = datetime.now(timezone.utc)
        await self.db.commit()

        logger.info(
            "External access revoked",
            extra={
                "access_id": str(access_id),
                "ticket_id": str(external_access.ticket_id),
                "revoked_by": str(current_user_id),
            },
        )

        return True

    async def list_external_accesses(
        self,
        ticket_id: UUID,
    ) -> list[ExternalAccessResponse]:
        """
        List all external accesses for a ticket.

        Args:
            ticket_id: UUID of the ticket

        Returns:
            List of ExternalAccessResponse objects
        """
        stmt = (
            select(TicketExternalAccess)
            .where(TicketExternalAccess.ticket_id == ticket_id)
            .order_by(TicketExternalAccess.created_at.desc())
        )
        result = await self.db.execute(stmt)
        accesses = result.scalars().all()

        return [
            ExternalAccessResponse(
                id=str(access.id),
                ticket_id=str(access.ticket_id),
                token=access.token,
                email=access.email,
                expires_at=access.expires_at,
                is_active=access.is_active,
                access_count=access.access_count,
                created_at=access.created_at,
                access_url=f"{settings.FRONTEND_URL}/external/tickets/{access.token}",
            )
            for access in accesses
        ]

    async def _send_external_access_email(
        self,
        external_access: TicketExternalAccess,
        ticket: Ticket,
        invited_by_user: User,
    ) -> None:
        """
        Send external access invitation email.

        Args:
            external_access: The external access record
            ticket: The ticket being shared
            invited_by_user: User who created the access
        """
        try:
            access_url = f"{settings.FRONTEND_URL}/external/tickets/{external_access.token}"

            context = {
                "recipient_email": external_access.email,
                "invited_by_name": invited_by_user.name or invited_by_user.email,
                "organization_name": ticket.organization.name
                if ticket.organization
                else "the organization",
                "ticket_title": ticket.title,
                "ticket_description": ticket.description or "",
                "ticket_priority": ticket.priority.value,
                "ticket_status": ticket.status.value.replace("_", " "),
                "project_name": ticket.project.title if ticket.project else None,
                "access_url": access_url,
                "expires_at": external_access.expires_at.strftime("%B %d, %Y")
                if external_access.expires_at
                else None,
            }

            await send_email(
                template_name="ticket_external_access_email",
                subject=f"You've been granted access to view: {ticket.title}",
                recipient=external_access.email,
                context=context,
            )

            logger.info(
                "External access email sent",
                extra={
                    "email": external_access.email,
                    "ticket_id": str(ticket.id),
                    "access_id": str(external_access.id),
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to send external access email: {str(e)}",
                exc_info=True,
                extra={
                    "email": external_access.email,
                    "ticket_id": str(ticket.id),
                },
            )
