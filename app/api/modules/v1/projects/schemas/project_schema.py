from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.modules.v1.users.schemas.user_schema import UserResponse


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Project title")
    description: Optional[str] = Field(None, description="Project description")
    master_prompt: Optional[str] = Field(None, description="High-level AI prompt for the project")


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    master_prompt: Optional[str] = None


class ProjectUserAssignment(BaseModel):
    user_ids: List[UUID] = Field(..., description="List of user IDs to assign to project")


class ProjectResponse(ProjectBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime
    assigned_users: List[UserResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectUserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role_id: UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
    page: int
    limit: int
    total_pages: Optional[int] = None
