"""Ticket Invitation Service"""

from typing import List, Tuple, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, BackgroundTasks
from datetime import datetime, timezone
import uuid
import logging

from app.api.modules.v1.tickets.models.invitation_model import TicketInvitation
from app.api.modules.v1.tickets.models.ticket import Ticket
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.tickets.schemas.invitation import InviteParticipantRequest
from app.api.core.dependencies.send_mail import send_email
from app.api.core.config import settings

logger = logging.getLogger("app")


async def get_ticket_with_access_check(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    user: User,
) -> Ticket:
    """
    Retrieve a ticket and verify user has access to it.

    Args:
        db: Database session
        ticket_id: UUID of the ticket
        user: Current user requesting access

    Returns:
        Ticket object

    Raises:
        HTTPException: If ticket not found or user doesn't have access
    """
    ticket = await db.scalar(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.organization_id == user.organization_id,
        )
    )

    if not ticket:
        logger.warning(
            f"Ticket {ticket_id} not found or user {user.id} doesn't have access"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or access denied",
        )

    return ticket


async def create_invitation(
    db: AsyncSession,
    ticket: Ticket,
    invitee_email: str,
    invited_by: User,
    expiry_hours: int = 48,
) -> TicketInvitation:
    """
    Create a new ticket invitation.

    Args:
        db: Database session
        ticket: Ticket to invite participant to
        invitee_email: Email address of the invitee
        invited_by: User creating the invitation
        expiry_hours: Hours until invitation expires

    Returns:
        Created TicketInvitation object
    """
    # Check if there's already an active invitation for this email
    existing_invitation = await db.scalar(
        select(TicketInvitation).where(
            TicketInvitation.ticket_id == ticket.id,
            TicketInvitation.invitee_email == invitee_email,
            TicketInvitation.is_revoked.is_(False),
            TicketInvitation.is_accepted.is_(False),
            TicketInvitation.expires_at > datetime.now(timezone.utc),
        )
    )

    if existing_invitation:
        logger.info(
            f"Active invitation already exists for {invitee_email} "
            f"on ticket {ticket.id}"
        )
        # Update the existing invitation with new expiry and token
        existing_invitation.token = TicketInvitation.generate_token()
        existing_invitation.expires_at = TicketInvitation.expiry_time(expiry_hours)
        existing_invitation.updated_at = datetime.now(timezone.utc)
        db.add(existing_invitation)
        await db.commit()
        await db.refresh(existing_invitation)
        return existing_invitation

    # Create new invitation
    invitation = TicketInvitation(
        ticket_id=ticket.id,
        invited_by=invited_by.id,
        invitee_email=invitee_email,
        token=TicketInvitation.generate_token(),
        expires_at=TicketInvitation.expiry_time(expiry_hours),
    )

    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    logger.info(
        f"Created invitation {invitation.id} for {invitee_email} "
        f"to ticket {ticket.id}"
    )

    return invitation


async def send_invitation_email(
    invitation: TicketInvitation,
    ticket: Ticket,
    invited_by: User,
    custom_message: Optional[str] = None,
) -> bool:
    """
    Send invitation email to participant.

    Args:
        invitation: TicketInvitation object
        ticket: Ticket object
        invited_by: User who created the invitation
        custom_message: Optional custom message from inviter

    Returns:
        True if email sent successfully, False otherwise
    """
    # Construct invitation link
    invitation_url = (
        f"{settings.FRONTEND_URL}/tickets/invite/accept?token={invitation.token}"
    )

    context = {
        "invitee_email": invitation.invitee_email,
        "inviter_name": invited_by.name or invited_by.email,
        "ticket_title": ticket.title,
        "ticket_id": str(ticket.id),
        "invitation_url": invitation_url,
        "expires_at": invitation.expires_at.strftime("%B %d, %Y at %I:%M %p UTC"),
        "custom_message": custom_message,
    }

    try:
        success = await send_email(
            template_name="ticket_invitation.html",
            subject=f"Invitation to collaborate on ticket: {ticket.title}",
            recipient=invitation.invitee_email,
            context=context,
        )

        if success:
            logger.info(
                f"Invitation email sent successfully to {invitation.invitee_email}"
            )
        else:
            logger.error(
                f"Failed to send invitation email to {invitation.invitee_email}"
            )

        return success

    except Exception as e:
        logger.error(
            f"Error sending invitation email to {invitation.invitee_email}: {str(e)}",
            exc_info=True,
        )
        return False


async def invite_participants(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    data: InviteParticipantRequest,
    current_user: User,
    background_tasks: BackgroundTasks,
) -> Tuple[List[TicketInvitation], List[dict]]:
    """
    Invite multiple participants to a ticket.

    Args:
        db: Database session
        ticket_id: UUID of the ticket
        data: Invitation request data
        current_user: User creating invitations
        background_tasks: FastAPI background tasks

    Returns:
        Tuple of (successful_invitations, failed_invitations)
    """
    # Verify ticket exists and user has access
    ticket = await get_ticket_with_access_check(db, ticket_id, current_user)

    successful_invitations = []
    failed_invitations = []

    for email in data.emails:
        try:
            # Create invitation
            invitation = await create_invitation(
                db=db,
                ticket=ticket,
                invitee_email=email,
                invited_by=current_user,
                expiry_hours=data.expiry_hours,
            )

            # Queue email sending in background
            background_tasks.add_task(
                send_invitation_email,
                invitation=invitation,
                ticket=ticket,
                invited_by=current_user,
                custom_message=data.message,
            )

            successful_invitations.append(invitation)
            logger.info(f"Successfully created invitation for {email}")

        except Exception as e:
            logger.error(f"Failed to create invitation for {email}: {str(e)}")
            failed_invitations.append(
                {
                    "email": email,
                    "error": str(e),
                }
            )

    return successful_invitations, failed_invitations


async def revoke_invitation(
    db: AsyncSession,
    invitation_id: uuid.UUID,
    current_user: User,
) -> TicketInvitation:
    """
    Revoke a ticket invitation.

    Args:
        db: Database session
        invitation_id: UUID of the invitation to revoke
        current_user: User revoking the invitation

    Returns:
        Revoked TicketInvitation object

    Raises:
        HTTPException: If invitation not found or user doesn't have access
    """
    # Fetch invitation and verify access
    invitation = await db.scalar(
        select(TicketInvitation).where(TicketInvitation.id == invitation_id)
    )

    if not invitation:
        logger.warning(f"Invitation {invitation_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Verify user has access to the ticket
    await get_ticket_with_access_check(db, invitation.ticket_id, current_user)

    if invitation.is_revoked:
        logger.warning(f"Invitation {invitation_id} is already revoked")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation is already revoked",
        )

    # Revoke the invitation
    invitation.revoke(current_user.id)
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    logger.info(f"Invitation {invitation_id} revoked by user {current_user.id}")

    return invitation


async def accept_invitation(
    db: AsyncSession,
    token: str,
    current_user: User,
) -> TicketInvitation:
    """
    Accept a ticket invitation using token.

    Args:
        db: Database session
        token: Unique invitation token
        current_user: User accepting the invitation

    Returns:
        Accepted TicketInvitation object

    Raises:
        HTTPException: If token invalid, expired, or already used
    """
    invitation = await db.scalar(
        select(TicketInvitation).where(TicketInvitation.token == token)
    )

    if not invitation:
        logger.warning("Invalid invitation token")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token",
        )

    # Check if invitation is valid
    if not invitation.is_valid():
        if invitation.is_revoked:
            detail = "This invitation has been revoked"
        elif invitation.is_accepted:
            detail = "This invitation has already been accepted"
        else:
            detail = "This invitation has expired"

        logger.warning(f"Invalid invitation {invitation.id}: {detail}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    # Verify email matches
    if invitation.invitee_email != current_user.email:
        logger.warning(
            f"User {current_user.email} attempting to accept invitation "
            f"meant for {invitation.invitee_email}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation is for a different email address",
        )

    # Accept the invitation
    invitation.accept()
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)

    logger.info(f"Invitation {invitation.id} accepted by user {current_user.id}")

    return invitation


async def get_ticket_invitations(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    current_user: User,
) -> List[TicketInvitation]:
    """
    Get all invitations for a ticket.

    Args:
        db: Database session
        ticket_id: UUID of the ticket
        current_user: Current user

    Returns:
        List of TicketInvitation objects

    Raises:
        HTTPException: If ticket not found or user doesn't have access
    """
    # Verify ticket exists and user has access
    await get_ticket_with_access_check(db, ticket_id, current_user)

    # Fetch all invitations for the ticket
    result = await db.exec(
        select(TicketInvitation)
        .where(TicketInvitation.ticket_id == ticket_id)
        .order_by(TicketInvitation.created_at.desc())
    )

    invitations = result.all()

    logger.info(f"Retrieved {len(invitations)} invitations for ticket {ticket_id}")

    return list(invitations)
