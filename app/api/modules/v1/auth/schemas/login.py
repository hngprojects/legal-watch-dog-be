from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, v):
        if not v or not str(v).strip():
            raise ValueError("Email cannot be empty")
        return v

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, v):
        if not v or not str(v).strip():
            raise ValueError("Password cannot be empty")
        return v


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class LogoutResponse(BaseModel):
    """Logout response schema."""

    message: str
    success: bool


class RefreshTokenResponse(BaseModel):
    """Token refresh response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Token refresh request schema."""

    refresh_token: str = Field(..., description="Valid refresh token")
