"""Ticket Invitation Routes"""

import logging
from fastapi import APIRouter, status, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api.modules.v1.tickets.service.invitation_service import (
    invite_participants,
    revoke_invitation,
    accept_invitation,
    get_ticket_invitations,
)
from app.api.modules.v1.tickets.schemas.invitation import (
    InviteParticipantRequest,
    InviteParticipantResponse,
    InvitationResponse,
    RevokeInvitationRequest,
    AcceptInvitationRequest,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.core.dependencies.auth import get_current_user
from app.api.utils.response_payloads import success_response
from app.api.db.database import get_db

router = APIRouter(prefix="/tickets", tags=["Ticket Invitations"])

logger = logging.getLogger(__name__)


@router.post(
    "/{ticket_id}/invite",
    response_model=InviteParticipantResponse,
    status_code=status.HTTP_200_OK,
)
async def invite_ticket_participants(
    ticket_id: str,
    payload: InviteParticipantRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invite participants to a ticket via email.

    Creates time-bound, revokable invitation links for each email address.
    Invitations expire after the specified duration (default 48 hours).

    Args:
        ticket_id: UUID of the ticket
        payload: Invitation request with emails and optional settings
        background_tasks: Background task manager for async email sending
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of successful and failed invitations

    Raises:
        404: Ticket not found or access denied
        400: Invalid ticket ID format
    """
    logger.info(
        f"User {current_user.id} inviting {len(payload.emails)} participants "
        f"to ticket {ticket_id}"
    )

    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        logger.warning(f"Invalid ticket_id format: {ticket_id}")
        return success_response(
            message="Invalid ticket ID format",
            status_code=status.HTTP_400_BAD_REQUEST,
            data={
                "successful_invites": [],
                "failed_invites": [{"error": "Invalid ticket ID format"}],
                "total_sent": 0,
            },
        )

    successful, failed = await invite_participants(
        db=db,
        ticket_id=ticket_uuid,
        data=payload,
        current_user=current_user,
        background_tasks=background_tasks,
    )

    # Convert to response format
    successful_responses = [
        InvitationResponse(
            id=str(inv.id),
            ticket_id=str(inv.ticket_id),
            invitee_email=inv.invitee_email,
            invited_by=str(inv.invited_by),
            expires_at=inv.expires_at,
            is_accepted=inv.is_accepted,
            is_revoked=inv.is_revoked,
            created_at=inv.created_at,
        )
        for inv in successful
    ]

    logger.info(
        f"Successfully invited {len(successful)} participants, "
        f"{len(failed)} failed for ticket {ticket_id}"
    )

    return success_response(
        message=f"Invitation emails sent to {len(successful)} recipients",
        status_code=status.HTTP_200_OK,
        data={
            "successful_invites": successful_responses,
            "failed_invites": failed,
            "total_sent": len(successful),
        },
    )


@router.post(
    "/invitations/revoke",
    response_model=InvitationResponse,
    status_code=status.HTTP_200_OK,
)
async def revoke_ticket_invitation(
    payload: RevokeInvitationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke a ticket invitation.

    Prevents the invitation from being accepted. The invitation link
    will no longer work.

    Args:
        payload: Request with invitation ID to revoke
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Revoked invitation details

    Raises:
        404: Invitation not found
        400: Invitation already revoked or invalid ID format
        403: User doesn't have access to revoke this invitation
    """
    logger.info(f"User {current_user.id} revoking invitation {payload.invitation_id}")

    try:
        invitation_uuid = uuid.UUID(payload.invitation_id)
    except ValueError:
        logger.warning(f"Invalid invitation_id format: {payload.invitation_id}")
        return success_response(
            message="Invalid invitation ID format",
            status_code=status.HTTP_400_BAD_REQUEST,
            data=None,
        )

    invitation = await revoke_invitation(
        db=db,
        invitation_id=invitation_uuid,
        current_user=current_user,
    )

    return success_response(
        message="Invitation revoked successfully",
        status_code=status.HTTP_200_OK,
        data={
            "id": str(invitation.id),
            "ticket_id": str(invitation.ticket_id),
            "invitee_email": invitation.invitee_email,
            "invited_by": str(invitation.invited_by),
            "expires_at": invitation.expires_at,
            "is_accepted": invitation.is_accepted,
            "is_revoked": invitation.is_revoked,
            "created_at": invitation.created_at,
        },
    )


@router.post(
    "/invitations/accept",
    response_model=InvitationResponse,
    status_code=status.HTTP_200_OK,
)
async def accept_ticket_invitation(
    payload: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept a ticket invitation using the token from the invitation email.

    This grants the user access to participate in the ticket.

    Args:
        payload: Request with invitation token
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Accepted invitation details

    Raises:
        404: Invalid token
        400: Invitation expired, revoked, or already accepted
        403: Token is for a different email address
    """
    logger.info(f"User {current_user.id} ({current_user.email}) accepting invitation")

    invitation = await accept_invitation(
        db=db,
        token=payload.token,
        current_user=current_user,
    )

    return success_response(
        message="Invitation accepted successfully",
        status_code=status.HTTP_200_OK,
        data={
            "id": str(invitation.id),
            "ticket_id": str(invitation.ticket_id),
            "invitee_email": invitation.invitee_email,
            "invited_by": str(invitation.invited_by),
            "expires_at": invitation.expires_at,
            "is_accepted": invitation.is_accepted,
            "is_revoked": invitation.is_revoked,
            "created_at": invitation.created_at,
        },
    )


@router.get(
    "/{ticket_id}/invitations",
    response_model=list[InvitationResponse],
    status_code=status.HTTP_200_OK,
)
async def list_ticket_invitations(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all invitations for a specific ticket.

    Returns all invitations (pending, accepted, revoked, and expired)
    for the specified ticket.

    Args:
        ticket_id: UUID of the ticket
        db: Database session
        current_user: Currently authenticated user

    Returns:
        List of all invitations for the ticket

    Raises:
        404: Ticket not found or access denied
        400: Invalid ticket ID format
    """
    logger.info(f"User {current_user.id} fetching invitations for ticket {ticket_id}")

    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        logger.warning(f"Invalid ticket_id format: {ticket_id}")
        return success_response(
            message="Invalid ticket ID format",
            status_code=status.HTTP_400_BAD_REQUEST,
            data=[],
        )

    invitations = await get_ticket_invitations(
        db=db,
        ticket_id=ticket_uuid,
        current_user=current_user,
    )

    invitations_data = [
        {
            "id": str(inv.id),
            "ticket_id": str(inv.ticket_id),
            "invitee_email": inv.invitee_email,
            "invited_by": str(inv.invited_by),
            "expires_at": inv.expires_at,
            "is_accepted": inv.is_accepted,
            "is_revoked": inv.is_revoked,
            "created_at": inv.created_at,
        }
        for inv in invitations
    ]

    return success_response(
        message=f"Retrieved {len(invitations)} invitations",
        status_code=status.HTTP_200_OK,
        data=invitations_data,
    )
