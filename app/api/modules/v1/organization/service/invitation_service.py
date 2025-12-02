import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.core.config import settings
from app.api.modules.v1.organization.models.invitation_model import Invitation, InvitationStatus

logger = logging.getLogger("app")


class InvitationCRUD:
    """CRUD operations for Invitation model."""

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        organization_id: uuid.UUID,
        organization_name: str,
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
                organization_name=organization_name,
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
    async def get_organization_invitations(
        db: AsyncSession,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        status_filter: Optional[str] = None,
    ) -> dict:
        """
        Get all invitations for an organization with pagination and filtering.

        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Optional status to filter by (e.g., 'pending', 'accepted', 'all')

        Returns:
            dict: Dictionary containing invitations list and total count
        """
        try:
            from app.api.modules.v1.users.models.users_model import User

            # Build base query
            query = select(Invitation).where(Invitation.organization_id == organization_id)

            # Build count query
            count_query = (
                select(func.count())
                .select_from(Invitation)
                .where(Invitation.organization_id == organization_id)
            )

            # Apply status filter if provided and not "all"
            if status_filter and status_filter.lower() != "all":
                status_filter_upper = status_filter.upper()
                if hasattr(InvitationStatus, status_filter_upper):
                    status_enum = InvitationStatus[status_filter_upper]
                    query = query.where(Invitation.status == status_enum)
                    count_query = count_query.where(Invitation.status == status_enum)

            # Order by most recent first
            query = query.order_by(Invitation.created_at.desc())

            # Get total count
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0

            # Apply pagination
            query = query.offset(skip).limit(limit)

            # Execute query
            result = await db.execute(query)
            invitations = result.scalars().all()

            # Format invitations for response
            formatted_invitations = []
            for invitation in invitations:
                # Get inviter details
                inviter = await db.get(User, invitation.inviter_id)

                # Calculate if invitation is expired
                is_expired = invitation.expires_at < datetime.now(timezone.utc)

                formatted_invitations.append(
                    {
                        "id": str(invitation.id),
                        "organization_id": str(invitation.organization_id),
                        "organization_name": invitation.organization_name,
                        "invited_email": invitation.invited_email,
                        "inviter_id": str(invitation.inviter_id),
                        "inviter_name": inviter.name if inviter else "Unknown",
                        "inviter_email": inviter.email if inviter else None,
                        "role_id": str(invitation.role_id) if invitation.role_id else None,
                        "role_name": invitation.role_name,
                        "status": invitation.status.value,
                        "is_expired": is_expired,
                        "expires_at": invitation.expires_at.isoformat(),
                        "accepted_at": invitation.accepted_at.isoformat()
                        if invitation.accepted_at
                        else None,
                        "created_at": invitation.created_at.isoformat(),
                        "updated_at": invitation.updated_at.isoformat(),
                    }
                )

            logger.info(
                f"Retrieved {len(formatted_invitations)} invitations for org_id={organization_id}"
            )

            return {
                "invitations": formatted_invitations,
                "total": total,
            }

        except Exception as e:
            logger.error(
                f"Failed to get invitations for org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve invitations")

    @staticmethod
    async def cancel_invitation(
        db: AsyncSession,
        invitation_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> Invitation:
        """
        Cancel a pending invitation.

        Args:
            db: Database session
            invitation_id: Invitation UUID to cancel
            requesting_user_id: User requesting the cancellation

        Returns:
            Updated invitation object

        Raises:
            ValueError: If invitation not found or cannot be cancelled
        """
        try:
            invitation = await db.get(Invitation, invitation_id)
            if not invitation:
                raise ValueError("Invitation not found")

            if invitation.status != InvitationStatus.PENDING:
                raise ValueError(f"Cannot cancel invitation with status: {invitation.status.value}")

            # Update status to cancelled
            invitation.status = InvitationStatus.CANCELLED
            invitation.updated_at = datetime.now(timezone.utc)

            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)

            logger.info(f"Cancelled invitation {invitation_id} by user {requesting_user_id}")
            return invitation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel invitation {invitation_id}: {str(e)}")
            raise Exception("Failed to cancel invitation")

    @staticmethod
    async def resend_invitation(
        db: AsyncSession,
        invitation_id: uuid.UUID,
        new_token: str,
    ) -> Invitation:
        """
        Resend an invitation by generating a new token and extending expiry.

        Args:
            db: Database session
            invitation_id: Invitation UUID to resend
            new_token: New unique token for the invitation

        Returns:
            Updated invitation object

        Raises:
            ValueError: If invitation cannot be resent
        """
        try:
            invitation = await db.get(Invitation, invitation_id)
            if not invitation:
                raise ValueError("Invitation not found")

            if invitation.status not in [InvitationStatus.PENDING, InvitationStatus.EXPIRED]:
                raise ValueError(f"Cannot resend invitation with status: {invitation.status.value}")

            # Update token, expiry, and status
            invitation.token = new_token
            invitation.status = InvitationStatus.PENDING
            invitation.expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.INVITATION_TOKEN_EXPIRE_MINUTES
            )
            invitation.updated_at = datetime.now(timezone.utc)

            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)

            logger.info(f"Resent invitation {invitation_id} with new token")
            return invitation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to resend invitation {invitation_id}: {str(e)}")
            raise Exception("Failed to resend invitation")
