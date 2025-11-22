from pydantic import BaseModel, EmailStr, Field


class ResendOTPRequest(BaseModel):
    """
    Request model for resending a registration OTP.

    Attributes:
        email: User's email address used during registration.
    """

    email: EmailStr = Field(..., description="User's email address")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "admin@techcorp.com",
            }
        }
