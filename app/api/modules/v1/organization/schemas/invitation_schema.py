import uuid
from datetime import datetime
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class InvitationCreate(SQLModel):
    invited_email: EmailStr = Field(description="Email of the user to invite")
    role_name: str = Field(
        default="Member", description="Role name (e.g., 'Admin', 'Member', 'Manager')"
    )


class InvitationResponse(SQLModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    invited_email: EmailStr
    inviter_id: uuid.UUID
    token: str
    role_id: Optional[uuid.UUID]
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
