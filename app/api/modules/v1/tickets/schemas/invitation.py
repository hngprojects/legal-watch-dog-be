"""Ticket Invitation Schemas"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class InviteParticipantRequest(BaseModel):
    """Request schema for inviting participants to a ticket"""

    emails: List[EmailStr] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of email addresses to invite (max 10 per request)",
    )
    expiry_hours: Optional[int] = Field(
        default=48,
        ge=1,
        le=168,
        description="Number of hours until invitation expires (1-168 hours, default 48)",
    )
    message: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional custom message to include in invitation email",
    )


class InvitationResponse(BaseModel):
    """Response schema for a single invitation"""

    id: str
    ticket_id: str
    invitee_email: str
    invited_by: str
    expires_at: datetime
    is_accepted: bool
    is_revoked: bool
    created_at: datetime

    class ConfigDict:
        from_attributes = True


class InviteParticipantResponse(BaseModel):
    """Response schema for bulk invitation"""

    successful_invites: List[InvitationResponse]
    failed_invites: List[dict]
    total_sent: int


class RevokeInvitationRequest(BaseModel):
    """Request schema for revoking an invitation"""

    invitation_id: str = Field(..., description="UUID of the invitation to revoke")


class AcceptInvitationRequest(BaseModel):
    """Request schema for accepting an invitation"""

    token: str = Field(..., description="Unique invitation token from email")
