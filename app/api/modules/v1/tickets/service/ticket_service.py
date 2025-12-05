import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.core.config import settings
from app.api.core.dependencies.auth import TenantGuard
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.organization.models.user_organization_model import (
    UserOrganization,
)
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketInvitedUser
from app.api.modules.v1.tickets.schemas.ticket_invitation_schema import (
    InvitedUserResponse,
    InviteUsersToTicketResponse,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class TicketService:
    """Service for handling ticket operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_users_to_ticket(
        self,
        ticket_id: UUID,
        emails: List[str],
        current_user_id: UUID,
    ) -> InviteUsersToTicketResponse:
        """
        Invite users to a ticket by their email addresses.

        Args:
            ticket_id: The UUID of the ticket
            emails: List of email addresses to invite
            current_user_id: The UUID of the current user making the request

        Returns:
            InviteUsersToTicketResponse with lists of invited, already_invited, and not_found emails

        Raises:
            ValueError: If ticket not found, user lacks permission,
              or user not member of organization
        """
        statement = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.invited_users),
                selectinload(Ticket.organization),
                selectinload(Ticket.project),
                selectinload(Ticket.created_by_user),
            )
        )
        result = await self.db.execute(statement)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise ValueError("Ticket not found")

        organization_id = ticket.organization_id

        current_user_result = await self.db.execute(select(User).where(User.id == current_user_id))
        current_user = current_user_result.scalar_one()

        tenant = TenantGuard(self.db, current_user)
        try:
            await tenant.get_membership(organization_id)
        except ValueError:
            raise ValueError(
                "You must be a member of the organization to invite users to this ticket"
            )

        has_permission = await check_user_permission(
            self.db,
            current_user_id,
            organization_id,
            "invite_participants",
        )
        if not has_permission:
            raise ValueError(
                "You do not have permission to invite users to tickets in this organization"
            )

        user_statement = (
            select(User)
            .join(UserOrganization, UserOrganization.user_id == User.id)
            .where(
                and_(
                    User.email.in_(emails),
                    UserOrganization.organization_id == organization_id,
                    UserOrganization.is_active,
                    not UserOrganization.is_deleted,
                    User.is_verified,
                    User.is_active,
                )
            )
        )
        user_result = await self.db.execute(user_statement)
        found_users = user_result.scalars().all()

        found_users_map = {user.email: user for user in found_users}
        already_invited_user_ids = {user.id for user in ticket.invited_users}

        invited: List[InvitedUserResponse] = []
        already_invited: List[str] = []
        not_found: List[str] = []

        for email in emails:
            user = found_users_map.get(email)

            if not user:
                not_found.append(email)
                continue

            if user.id in already_invited_user_ids:
                already_invited.append(email)
                continue

            invitation = TicketInvitedUser(
                ticket_id=ticket_id,
                user_id=user.id,
                invited_at=datetime.now(timezone.utc),
            )
            self.db.add(invitation)

            await self._send_invitation_email(
                ticket=ticket,
                invited_user=user,
                invited_by_user=current_user,
            )

            invited.append(
                InvitedUserResponse(
                    user_id=str(user.id),
                    email=user.email,
                    name=user.name,
                    invited_at=invitation.invited_at,
                )
            )

            logger.info(f"User {user.id} ({user.email}) invited to ticket {ticket_id}")

        if invited:
            await self.db.commit()

        return InviteUsersToTicketResponse(
            invited=invited,
            already_invited=already_invited,
            not_found=not_found,
        )

    async def _send_invitation_email(
        self,
        ticket: Ticket,
        invited_user: User,
        invited_by_user: User,
    ) -> None:
        """
        Send invitation email to a user invited to a ticket.

        Args:
            ticket: The ticket object with loaded relationships
            invited_user: The user being invited
            invited_by_user: The user who sent the invitation
        """
        try:
            ticket_link = f"{settings.FRONTEND_URL}/tickets/{ticket.id}"

            context = {
                "recipient_name": invited_user.name or invited_user.email,
                "invited_by_name": (f"{invited_by_user.name}".strip() or invited_by_user.email),
                "organization_name": ticket.organization.name
                if ticket.organization
                else "the organization",
                "ticket_title": ticket.title,
                "ticket_description": ticket.description or "",
                "ticket_priority": ticket.priority.value,
                "ticket_status": ticket.status.value.replace("_", " "),
                "project_name": ticket.project.title if ticket.project else None,
                "ticket_link": ticket_link,
            }

            await send_email(
                template_name="ticket_invitation_email",
                subject=f"You've been invited to collaborate on a ticket: {ticket.title}",
                recipient=invited_user.email,
                context=context,
            )

            logger.info(f"Invitation email sent to {invited_user.email} for ticket {ticket.id}")

        except Exception as e:
            logger.error(
                f"Failed to send invite to {invited_user.email} for ticket {ticket.id}: {str(e)}",
                exc_info=True,
            )
