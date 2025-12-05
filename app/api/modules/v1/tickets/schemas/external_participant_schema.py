from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, Field


class InviteParticipantsRequest(BaseModel):
    """Request schema for inviting participants (internal users + external) to a ticket"""

    emails: List[EmailStr] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of email addresses to invite (internal users or external participants)",
    )
    role: str = Field(
        default="Guest",
        max_length=100,
        description="Role description for external participants (e.g., 'Legal Counsel')",
    )
    expiry_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Number of days until external guest access expires",
    )


class InternalUserInvitationResponse(BaseModel):
    """Response for internal user notification (they log in normally)"""

    user_id: str
    email: str
    name: str | None
    is_internal: bool = True
    invited_at: datetime

    class Config:
        from_attributes = True


class ExternalParticipantResponse(BaseModel):
    """Response schema for an invited external participant (guest access)"""

    participant_id: str
    email: str
    role: str
    is_internal: bool = False
    invited_at: datetime
    expires_at: datetime | None
    magic_link: str | None = Field(
        None,
        description="The magic link sent to the participant (only returned on creation)",
    )

    class Config:
        from_attributes = True


class InviteParticipantsResponse(BaseModel):
    """Response schema for inviting participants (both internal and external)"""

    internal_users: List[InternalUserInvitationResponse] = Field(
        ..., description="Internal users notified (they'll log in normally)"
    )
    external_participants: List[ExternalParticipantResponse] = Field(
        ..., description="External participants with guest access (magic link)"
    )
    already_invited: List[str] = Field(
        ..., description="Email addresses that were already invited"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "internal_users": [
                    {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "john@company.com",
                        "name": "John Doe",
                        "is_internal": True,
                        "invited_at": "2025-12-05T10:30:00Z",
                    }
                ],
                "external_participants": [
                    {
                        "participant_id": "123e4567-e89b-12d3-a456-426614174001",
                        "email": "counsel@lawfirm.com",
                        "role": "Legal Counsel",
                        "is_internal": False,
                        "invited_at": "2025-12-05T10:30:00Z",
                        "expires_at": "2025-12-12T10:30:00Z",
                        "magic_link": "https://app.legalwatchdog.com/guest/access?token=eyJ...",
                    }
                ],
                "already_invited": ["existing@company.com"],
            }
        }


class GuestTicketAccessResponse(BaseModel):
    """Response schema for guest ticket access (limited view)"""

    ticket_id: str
    title: str
    description: str | None
    priority: str
    status: str
    created_at: datetime
    project_name: str | None

    # Guest-specific info
    participant_email: str
    participant_role: str
    access_expires_at: datetime | None

    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Legal Review Required for Contract Amendment",
                "description": "We need external counsel to review...",
                "priority": "high",
                "status": "open",
                "created_at": "2025-12-05T10:00:00Z",
                "project_name": "Contract Management System",
                "participant_email": "counsel@lawfirm.com",
                "participant_role": "Legal Counsel",
                "access_expires_at": "2025-12-12T10:30:00Z",
            }
        }
