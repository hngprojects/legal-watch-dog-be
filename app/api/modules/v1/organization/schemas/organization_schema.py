from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateOrganizationRequest(BaseModel):
    """Schema for creating a new organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    industry: str | None = Field(None, max_length=100, description="Industry type")

    class Config:
        json_schema_extra = {"example": {"name": "Acme Corporation", "industry": "Technology"}}


class CreateOrganizationResponse(BaseModel):
    """Schema for organization response data."""

    organization_id: str
    organization_name: str
    user_id: str
    role: str
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                "organization_name": "Acme Corporation",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "role": "admin",
                "message": "Organization created successfully",
            }
        }


class UpdateOrganizationRequest(BaseModel):
    """Schema for updating an organization."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Organization name")
    industry: Optional[str] = Field(None, max_length=100, description="Industry type")
    is_active: Optional[bool] = Field(None, description="Organization active status")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation Updated",
                "industry": "Software Development",
                "is_active": True,
            }
        }


class OrganizationDetailResponse(BaseModel):
    """Schema for organization detail response."""

    id: str
    name: str
    industry: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    settings: dict
    billing_info: dict

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Acme Corporation",
                "industry": "Technology",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "settings": {},
                "billing_info": {},
            }
        }
