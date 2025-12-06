import logging
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.core.config import settings
from app.api.core.dependencies.auth import TenantGuard
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.tickets.models.ticket_model import ExternalParticipant, Ticket
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    ExternalParticipantResponse,
    InternalUserInvitationResponse,
    InviteParticipantsResponse,
)
from app.api.modules.v1.tickets.utils.guest_token import (
    create_guest_token,
    hash_token,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class ParticipantService:
    """Service for handling ticket participant invitations (internal users + external guests)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_participants(
        self,
        ticket_id: UUID,
        emails: List[str],
        role: str,
        expiry_days: int,
        current_user_id: UUID,
    ) -> InviteParticipantsResponse:
        """
        Invite participants to a ticket (BOTH internal users AND external participants).

        UNIFIED INVITATION SYSTEM:
        - Checks if email exists in users table
        - If YES (internal user):
          → Send notification email with regular ticket link
          → They log in normally to view ticket
        - If NO (external participant):
          → Create ExternalParticipant record
          → Generate JWT magic link
          → Send guest access email

        Args:
            ticket_id: The UUID of the ticket
            emails: List of email addresses (internal or external)
            role: Role description for external participants
            expiry_days: Expiration for external guest access (internal users don't expire)
            current_user_id: The UUID of the current user making the request

        Returns:
            InviteParticipantsResponse with internal_users,
            external_participants, and already_invited

        Raises:
            ValueError: If ticket not found, user lacks permission, or user not member of org
        """

        statement = (
            select(Ticket)
            .where(Ticket.id == ticket_id)
            .options(
                selectinload(Ticket.invited_users),
                selectinload(Ticket.organization),
                selectinload(Ticket.project),
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
                "You must be a member of the organization to invite participants to this ticket"
            )

        has_permission = await check_user_permission(
            self.db,
            current_user_id,
            organization_id,
            "invite_participants",
        )
        if not has_permission:
            raise ValueError(
                "You do not have permission to invite participants to tickets in this organization"
            )

        existing_external_emails = {p.email.lower() for p in ticket.invited_users}

        normalized_emails = [email.strip().lower() for email in emails]

        user_statement = select(User).where(
            and_(
                User.email.in_(normalized_emails),
                User.is_active,
                User.is_verified,
            )
        )
        user_result = await self.db.execute(user_statement)
        found_users = user_result.scalars().all()

        users_by_email = {user.email.lower(): user for user in found_users}

        internal_users: List[InternalUserInvitationResponse] = []
        external_participants: List[ExternalParticipantResponse] = []
        already_invited: List[str] = []

        for email in normalized_emails:
            if email in existing_external_emails:
                already_invited.append(email)
                continue

            user = users_by_email.get(email)

            if user:
                # INTERNAL USER - Send notification email
                await self._send_internal_user_notification(
                    ticket=ticket,
                    user=user,
                    invited_by_user=current_user,
                )

                internal_users.append(
                    InternalUserInvitationResponse(
                        user_id=str(user.id),
                        email=user.email,
                        name=user.name or "" or None,
                        is_internal=True,
                        invited_at=datetime.now(timezone.utc),
                    )
                )

                logger.info(
                    f"Internal user {user.id} ({user.email}) notified about ticket {ticket_id}"
                )

            else:
                # EXTERNAL PARTICIPANT - Create guest access with magic link
                expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

                participant = ExternalParticipant(
                    ticket_id=ticket_id,
                    email=email,
                    role=role,
                    invited_by_user_id=current_user_id,
                    invited_at=datetime.now(timezone.utc),
                    is_active=True,
                    expires_at=expires_at,
                )
                self.db.add(participant)
                await self.db.flush()
                await self.db.refresh(participant)

                token = create_guest_token(
                    participant_id=participant.id,
                    ticket_id=ticket_id,
                    expiry_days=expiry_days,
                )

                participant.token_hash = hash_token(token)
                self.db.add(participant)

                magic_link = f"{settings.FRONTEND_URL}/guest/access?token={token}"

                await self._send_external_participant_email(
                    ticket=ticket,
                    participant_email=email,
                    participant_role=role,
                    invited_by_user=current_user,
                    magic_link=magic_link,
                    expires_at=expires_at,
                )

                external_participants.append(
                    ExternalParticipantResponse(
                        participant_id=str(participant.id),
                        email=email,
                        role=role,
                        is_internal=False,
                        invited_at=participant.invited_at,
                        expires_at=expires_at,
                        magic_link=magic_link,
                    )
                )

                logger.info(
                    f"External participant {email} invited to ticket {ticket_id} (guest access)"
                )

        if internal_users or external_participants:
            await self.db.commit()

        return InviteParticipantsResponse(
            internal_users=internal_users,
            external_participants=external_participants,
            already_invited=already_invited,
        )

    async def _send_internal_user_notification(
        self,
        ticket: Ticket,
        user: User,
        invited_by_user: User,
    ) -> None:
        """
        Send notification email to internal user (they'll log in normally).

        IMPORTANT: This is NOT a magic link. Internal users log in normally
        and access the ticket through the regular authenticated dashboard.

        Args:
            ticket: The ticket object
            user: The internal user being notified
            invited_by_user: User who sent the invitation
        """
        try:
            ticket_link = f"{settings.FRONTEND_URL}/tickets/{ticket.id}"

            context = {
                "recipient_name": user.name or user.email,
                "invited_by_name": (invited_by_user.name or invited_by_user.email),
                "organization_name": (
                    ticket.organization.name if ticket.organization else "the organization"
                ),
                "ticket_title": ticket.title,
                "ticket_description": ticket.description or "",
                "ticket_priority": ticket.priority.value,
                "ticket_status": ticket.status.value.replace("_", " "),
                "project_name": ticket.project.title if ticket.project else None,
                "ticket_link": ticket_link,
                "is_internal": True,
            }

            await send_email(
                template_name="internal_user_ticket_notification.html",
                subject=f"You've been invited to collaborate: {ticket.title}",
                recipient=user.email,
                context=context,
            )

            logger.info(f"Internal user notification sent to {user.email} for ticket {ticket.id}")

        except Exception as e:
            logger.error(
                f"Failed to send notification to {user.email} for ticket {ticket.id}: {str(e)}",
                exc_info=True,
            )

    async def _send_external_participant_email(
        self,
        ticket: Ticket,
        participant_email: str,
        participant_role: str,
        invited_by_user: User,
        magic_link: str,
        expires_at: datetime,
    ) -> None:
        """
        Send guest access email to external participant with magic link.

        CRITICAL: The magic link must go to /guest/access?token=xyz
        NOT to /tickets/{id} (which requires login).

        Args:
            ticket: The ticket object
            participant_email: Email of the external participant
            participant_role: Role of the participant
            invited_by_user: User who sent the invitation
            magic_link: The magic link with JWT token
            expires_at: When the access expires
        """
        try:
            recipient_name = participant_email.split("@")[0].title()

            context = {
                "recipient_name": recipient_name,
                "recipient_role": participant_role,
                "invited_by_name": (invited_by_user.name or invited_by_user.email),
                "organization_name": (
                    ticket.organization.name if ticket.organization else "the organization"
                ),
                "ticket_title": ticket.title,
                "ticket_description": ticket.description or "",
                "ticket_priority": ticket.priority.value,
                "ticket_status": ticket.status.value.replace("_", " "),
                "project_name": ticket.project.title if ticket.project else None,
                "magic_link": magic_link,  # CRITICAL: Guest access link
                "expires_at": expires_at.strftime("%B %d, %Y"),
                "is_external": True,
            }

            await send_email(
                template_name="external_participant_invitation.html",
                subject=f"You've been invited to collaborate: {ticket.title}",
                recipient=participant_email,
                context=context,
            )

            logger.info(
                f"External participant email sent to {participant_email} for ticket {ticket.id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to send email to {participant_email} for ticket {ticket.id}: {str(e)}",
                exc_info=True,
            )
