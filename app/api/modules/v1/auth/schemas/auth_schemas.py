"""
Authentication request and response schemas.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uuid


class LoginRequest(BaseModel):
    """
    Request schema for user login.
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")


class TokenData(BaseModel):
    """
    Token data embedded in JWT.
    """
    user_id: uuid.UUID
    organisation_id: uuid.UUID
    role: str
    email: str


class LoginResponse(BaseModel):
    """
    Response schema for successful login.
    """
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: dict = Field(..., description="User information")


class RefreshTokenRequest(BaseModel):
    """
    Request schema for token refresh.
    """
    refresh_token: str = Field(..., description="Valid refresh token")


class RefreshTokenResponse(BaseModel):
    """
    Response schema for successful token refresh.
    """
    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")


class LogoutResponse(BaseModel):
    """
    Response schema for successful logout.
    """
    message: str = Field(default="Logged out successfully")


class ErrorResponse(BaseModel):
    """
    Generic error response schema.
    """
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[list[str]] = Field(None, description="Additional error details")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
