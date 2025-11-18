from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from uuid import UUID

# Request Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Response Schemas
class UserResponse(BaseModel):
    user_id: UUID
    email: str
    status: str
    
    class Config:
        from_attributes = True

class RoleResponse(BaseModel):
    role_id: UUID
    name: str
    
    class Config:
        from_attributes = True

class OrganizationResponse(BaseModel):
    org_id: UUID
    name: str
    industry: Optional[str]
    
    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    data: dict
    
    class Config:
        from_attributes = True