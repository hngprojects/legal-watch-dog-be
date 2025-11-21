from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RegulatorySourceBase(BaseModel):
    project_id: UUID = Field(..., description="ID of the project this source belongs to")
    source_type: str = Field(
        ..., min_length=1, max_length=100,
        description="Type of regulatory source (e.g., 'URL', 'PDF', 'Text')"
    )
    value: str = Field(
        ..., min_length=1, max_length=500,
        description="The actual regulatory value (URL, text content, etc.)"
    )


class RegulatorySourceCreate(RegulatorySourceBase):
    """Schema used when creating a new regulatory source."""
    pass


class RegulatorySourceUpdate(BaseModel):
    """Schema used when updating an existing regulatory source."""
    source_type: Optional[str] = Field(None, max_length=100)
    value: Optional[str] = Field(None, max_length=500)


class RegulatorySourceResponse(RegulatorySourceBase):
    """Schema returned to the client."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
