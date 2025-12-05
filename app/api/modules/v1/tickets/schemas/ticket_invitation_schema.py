from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator


class InviteUsersToTicketRequest(BaseModel):
    """Request schema for inviting users to a ticket"""

    emails: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of email addresses to invite to the ticket",
    )

    @field_validator("emails")
    def validate_emails(cls, emails: List[str]):
        """Minimal validation: must contain @ and . and be unique"""

        if not emails:
            raise ValueError("At least one email address is required")

        # Check duplicates
        if len(emails) != len(set(emails)):
            raise ValueError("Duplicate email addresses are not allowed")

        validated = []

        for email in emails:
            email = email.strip()

            if not email:
                raise ValueError("Email cannot be empty")

            if "@" not in email:
                raise ValueError(f"Invalid email '{email}': missing '@'")

            local_domain = email.split("@", 1)

            if len(local_domain) != 2:
                raise ValueError(f"Invalid email '{email}'")

            domain = local_domain[1]

            if "." not in domain:
                raise ValueError(f"Invalid email '{email}': missing '.' in domain")

            validated.append(email)

        return validated


class InvitedUserResponse(BaseModel):
    """Response schema for an invited user"""

    user_id: str
    email: str
    name: str | None
    invited_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "name": "John",
                "invited_at": "2025-01-15T10:30:00Z",
            }
        }


class InviteUsersToTicketResponse(BaseModel):
    """Response schema for ticket invitation operation"""

    invited: List[InvitedUserResponse] = Field(
        ..., description="Users successfully invited to the ticket"
    )
    already_invited: List[str] = Field(
        ..., description="Email addresses that were already invited to this ticket"
    )
    not_found: List[str] = Field(
        ...,
        description="Email addresses that don't exist in the organization",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "invited": [
                    {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "user1@example.com",
                        "name": "John",
                        "invited_at": "2025-01-15T10:30:00Z",
                    }
                ],
                "already_invited": ["user2@example.com"],
                "not_found": ["nonexistent@example.com"],
            }
        }
