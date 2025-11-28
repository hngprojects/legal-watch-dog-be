from typing import Dict, Optional

from pydantic import BaseModel, EmailStr, Field


class SpecialistHireRequest(BaseModel):
    company_name: str = Field(..., max_length=255)
    company_email: EmailStr
    industry: str = Field(..., max_length=255)
    brief_description: str = Field(...)


class SpecialistHireResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None
