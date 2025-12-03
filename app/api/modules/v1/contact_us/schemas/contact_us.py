from datetime import datetime
from typing import List
from uuid import UUID

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.api.utils.validators import is_company_email


class ContactUsRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    phone_number: str = Field(..., min_length=10, max_length=20)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        try:
            p = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(p):
                region = phonenumbers.region_code_for_number(p)
                if region:
                    raise ValueError(f"Invalid phone number (Country: {region})")
                else:
                    raise ValueError("Invalid phone number format")
            return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            raise ValueError("Invalid phone number format")

    @field_validator("email")
    @classmethod
    def email_must_be_company(cls, v):
        if not is_company_email(v):
            raise ValueError("Only company email addresses are allowed.")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ContactUsDetail(BaseModel):
    """Schema for individual contact submission details"""

    id: UUID
    full_name: str
    email: str
    phone_number: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactUsResponse(BaseModel):
    message: str
    email: EmailStr


class ContactUsListResponse(BaseModel):
    """Response schema for GET all contacts"""

    contacts: List[ContactUsDetail]
    total: int
    page: int
    limit: int
    total_pages: int
