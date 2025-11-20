"""
Project Schemas
Pydantic models for request/response validation
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProjectCreateRequest(BaseModel):
    """Request schema for creating a new project"""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    master_prompt: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty.")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Description cannot be empty.")
        return v


class ProjectUpdateRequest(BaseModel):
    """Request schema for updating project"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    master_prompt: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Title cannot be empty.")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Description cannot be empty.")
        return v


class ProjectResponse(BaseModel):
    """Response schema for project data"""

    id: UUID
    title: str
    description: str
    master_prompt: Optional[str] = None
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ProjectListResponse(BaseModel):
    """Response schema for paginated project list"""

    data: List[ProjectResponse]
    total: int
    page: int
    limit: int
    total_pages: int
