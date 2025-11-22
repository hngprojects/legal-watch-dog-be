"""Schemas For Jurisdiction Request and Responses"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JurisdictionCreateSchema(BaseModel):
    """Schema for creating a Jurisdiction"""

    project_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: str
    prompt: Optional[str] = None
    scrape_output: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class JurisdictionResponseSchema(BaseModel):
    """Schema used for returning Jurisdiction objects in responses"""

    id: UUID
    project_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: str
    prompt: Optional[str] = None
    scrape_output: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    is_deleted: bool = False

    model_config = ConfigDict(from_attributes=True)


class JurisdictionUpdateSchema(BaseModel):
    """Schema for updating a jurisdiction: all fields optional except id"""

    parent_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    scrape_output: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    is_deleted: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)
