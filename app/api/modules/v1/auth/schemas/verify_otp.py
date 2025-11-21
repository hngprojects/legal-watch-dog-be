from pydantic import BaseModel, EmailStr, Field


class VerifyOTPRequest(BaseModel):
    """
    Request model for OTP verification.

    Attributes:
        email: User's email address
        code: 6-digit OTP code sent to email
    """

    email: EmailStr = Field(..., description="User's email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

    class Config:
        json_schema_extra = {"example": {"email": "admin@techcorp.com", "code": "123456"}}


class VerifyOTPResponse(BaseModel):
    """
    Response model for successful OTP verification.

    Attributes:
        organization_id: Created organization ID
        organization_name: Organization name
        email: User email
        user_id: Created user ID
    """

    organization_id: int
    organization_name: str
    email: EmailStr
    user_id: int

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": 1,
                "organization_name": "Tech Corp",
                "email": "admin@techcorp.com",
                "user_id": 1,
            }
        }
