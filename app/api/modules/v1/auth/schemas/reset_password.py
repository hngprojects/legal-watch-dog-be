from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing_extensions import Self


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Email address cannot be empty")
        return v.strip()


class PasswordResetVerify(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    code: str = Field(
        ..., min_length=6, max_length=6, description="6-digit verification code"
    )

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Email address cannot be empty")
        return v.strip()

    @field_validator("code", mode="before")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Reset code cannot be empty")
        if not v.isdigit():
            raise ValueError("Reset code must contain only digits")
        if len(v) != 6:
            raise ValueError("Reset code must be exactly 6 digits")
        return v


class PasswordResetConfirm(BaseModel):
    reset_token: str = Field(..., description="Temporary reset token from verify step")
    new_password: str = Field(
        ..., min_length=8, max_length=100, description="New password (min 8 characters)"
    )
    confirm_password: str = Field(..., description="Confirm new password")

    @field_validator("reset_token", mode="before")
    @classmethod
    def validate_reset_token(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Reset token cannot be empty")
        return v.strip()

    @field_validator("new_password", mode="before")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("New password cannot be empty")
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters long")
        return v

    @field_validator("confirm_password", mode="before")
    @classmethod
    def validate_confirm_password(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Password confirmation cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self) -> Self:
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
