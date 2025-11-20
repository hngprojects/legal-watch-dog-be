from pydantic import BaseModel, EmailStr, Field, field_validator


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")


class PasswordResetVerify(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Code must contain only digits")
        return v


class PasswordResetConfirm(BaseModel):
    reset_token: str = Field(..., description="Temporary reset token from verify step")
    new_password: str = Field(
        ..., min_length=8, max_length=100, description="New password (min 8 characters)"
    )
    confirm_password: str = Field(..., description="Confirm new password")
