from uuid import UUID

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role_id: UUID
    is_active: bool

    class Config:
        from_attributes = True