from pydantic import BaseModel, EmailStr, Field, field_validator

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
        cleaned = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not cleaned.replace("+", "").isdigit():
            raise ValueError("Phone number must contain only digits and optional '+'")
        if len(cleaned) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        return v.strip()

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


class ContactUsResponse(BaseModel):
    message: str
    email: EmailStr
