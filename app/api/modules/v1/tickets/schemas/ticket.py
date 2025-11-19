from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TicketCreateRequest(BaseModel):
    """Request schema for creating a new ticket"""

    title: str = Field(..., max_length=255, description="Ticket title")
    description: Optional[str] = Field(None, description="Detailed ticket description")
    project_id: str = Field(
        ..., description="UUID of the project this ticket belongs to"
    )
    assigned_to: Optional[str] = Field(
        None, description="UUID of the user to assign the ticket to"
    )
    priority: Optional[str] = Field(
        default="medium",
        description="Ticket priority: low, medium, high, critical",
    )
    status: Optional[str] = Field(
        default="open",
        description="Ticket status: open, in_progress, resolved, closed",
    )


class TicketResponse(BaseModel):
    """Response schema for ticket data"""

    id: str
    organization_id: str
    project_id: str
    created_by: str
    assigned_to: Optional[str]
    title: str
    description: Optional[str]
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

    class ConfigDict:
        from_attributes = True
