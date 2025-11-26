import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.organization.models.invitation_model import Invitation, InvitationStatus

logger = logging.getLogger("app")


class InvitationCRUD:
    """CRUD operations for Invitation model."""

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        organization_id: uuid.UUID,
        invited_email: str,
        inviter_id: uuid.UUID,
        token: str,
        role_id: Optional[uuid.UUID] = None,
        role_name: Optional[str] = None,
        status: InvitationStatus = InvitationStatus.PENDING,
    ) -> Invitation:
        """
        Create a new invitation.
        """
        try:
            invitation = Invitation(
                organization_id=organization_id,
                invited_email=invited_email,
                inviter_id=inviter_id,
                token=token,
                role_id=role_id,
                role_name=role_name,
                status=status,
            )

            logger.info(
                "Created invitation: id=%s, org_id=%s, invited_email=%s, token=%s",
                invitation.id,
                invitation.organization_id,
                invitation.invited_email,
                token,
            )
            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)
            logger.info(
                "Created invitation: id=%s, org_id=%s, invited_email=%s",
                invitation.id,
                invitation.organization_id,
                invitation.invited_email,
            )
            return invitation
        except Exception as e:
            logger.error("Failed to create invitation for email=%s: %s", invited_email, str(e))
            raise Exception("Failed to create invitation")

    @staticmethod
    async def get_invitation_by_token(db: AsyncSession, token: str) -> Optional[Invitation]:
        """
        Get an invitation by its token.
        """
        result = await db.execute(select(Invitation).where(Invitation.token == token))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_invitation_status(
        db: AsyncSession,
        invitation_id: uuid.UUID,
        status: InvitationStatus,
        accepted_at: Optional[datetime] = None,
    ) -> Invitation:
        """
        Update the status of an invitation.
        """
        try:
            invitation = await db.get(Invitation, invitation_id)
            if not invitation:
                raise ValueError(f"Invitation with ID {invitation_id} not found.")
            invitation.status = status
            invitation.updated_at = datetime.now(timezone.utc)

            if status == InvitationStatus.ACCEPTED and accepted_at:
                invitation.accepted_at = accepted_at

            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)
            logger.info("Updated invitation %s status to %s", invitation_id, status)
            return invitation

        except Exception as e:
            logger.error("Failed to update invitation %s: %s", invitation_id, str(e))
            await db.rollback()
            raise Exception("Failed to update invitation")

    @staticmethod
    async def get_pending_invitations_for_user_email(
        db: AsyncSession, email: str
    ) -> list[Invitation]:
        """
        Get all pending invitations for a specific email address.
        """

        try:
            result = await db.execute(
                select(Invitation).where(
                    Invitation.invited_email == email,
                    Invitation.status == InvitationStatus.PENDING,
                    Invitation.expires_at > datetime.now(timezone.utc),
                )
            )
            invitations = list(result.scalars().all())

            valid_invitations = [
                inv for inv in invitations if not await InvitationCRUD._is_invitation_expired(inv)
            ]

            return valid_invitations
        except Exception as e:
            logger.error("Failed to get pending invitations for email=%s: %s", email, str(e))
            raise Exception("Failed to get invitations")

    @staticmethod
    async def _is_invitation_expired(invitation: Invitation) -> bool:
        """
        Check if an invitation has expired.
        """
        return invitation.expires_at < datetime.now(timezone.utc)

    @staticmethod
    async def expire_invitation(db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
        """
        Explicitly expire an invitation.
        """
        return await InvitationCRUD.update_invitation_status(
            db, invitation_id, InvitationStatus.EXPIRED
        )

    @staticmethod
    async def cancel_invitation(db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
        """
        Cancel an invitation.
        """
        return await InvitationCRUD.update_invitation_status(
            db, invitation_id, InvitationStatus.CANCELLED
        )
