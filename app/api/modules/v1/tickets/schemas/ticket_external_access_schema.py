from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateExternalAccessRequest(BaseModel):
    """Request schema for creating external ticket access."""

    email: Optional[EmailStr] = Field(
        None,
        description="Email of external user (optional, for tracking and notifications)",
    )
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Number of days until access expires (None for permanent)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "external@partner.com",
                "expires_in_days": 30,
            }
        }


class ExternalAccessResponse(BaseModel):
    """Response schema for external ticket access."""

    id: str
    ticket_id: str
    token: str
    email: Optional[str]
    expires_at: Optional[datetime]
    is_active: bool
    access_count: int
    created_at: datetime
    access_url: str

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "ticket_id": "123e4567-e89b-12d3-a456-426614174001",
                "token": "ext_abc123def456...",
                "email": "external@partner.com",
                "expires_at": "2025-02-05T10:30:00Z",
                "is_active": True,
                "access_count": 5,
                "created_at": "2025-01-05T10:30:00Z",
                "access_url": "https://app.example.com/external/tickets/ext_abc123def456...",
            }
        }


class ExternalTicketDetailResponse(BaseModel):
    """Response schema for external ticket view (limited data)."""

    id: str
    title: str
    description: Optional[str]
    content: Optional[str]
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    organization_name: str
    project_name: str

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "title": "Change Detected in Regulation XYZ",
                "description": "Automatic ticket created from data revision...",
                "content": "Detailed content here...",
                "status": "open",
                "priority": "high",
                "created_at": "2025-01-05T10:30:00Z",
                "updated_at": "2025-01-05T10:30:00Z",
                "organization_name": "Legal Corp",
                "project_name": "Compliance Monitoring",
            }
        }


class RevokeExternalAccessRequest(BaseModel):
    """Request schema for revoking external access."""

    access_id: UUID = Field(..., description="ID of the external access to revoke")

    class Config:
        json_schema_extra = {
            "example": {
                "access_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
