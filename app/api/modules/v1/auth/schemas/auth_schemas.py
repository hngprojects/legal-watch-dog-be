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
    Tokens are now set in HttpOnly cookies, not returned in response body.
    """
    message: str = Field(default="Login successful", description="Success message")
    user: dict = Field(..., description="User information")


class RefreshTokenRequest(BaseModel):
    """
    Request schema for token refresh.
    Refresh token is now read from HttpOnly cookie, not from request body.
    """
    pass


class RefreshTokenResponse(BaseModel):
    """
    Response schema for successful token refresh.
    Tokens are now set in HttpOnly cookies, not returned in response body.
    """
    message: str = Field(default="Token refreshed successfully", description="Success message")


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
