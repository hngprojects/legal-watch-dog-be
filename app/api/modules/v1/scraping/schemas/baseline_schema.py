"""
Schemas for Baseline Acceptance functionality.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaselineAcceptanceRequest(BaseModel):
    """Request schema for accepting a revision as baseline."""

    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional notes explaining why this baseline was accepted"
    )


class BaselineResponse(BaseModel):
    """Response schema for baseline revision data."""

    id: UUID
    source_id: UUID
    is_baseline: bool
    baseline_accepted_at: Optional[datetime]
    baseline_accepted_by: Optional[UUID]
    baseline_notes: Optional[str]
    scraped_at: datetime
    ai_summary: Optional[str]
    ai_markdown_summary: Optional[str]
    was_change_detected: bool

    model_config = ConfigDict(from_attributes=True)


class BaselineHistoryResponse(BaseModel):
    """Response schema for baseline history listing."""

    revisions: list[BaselineResponse]
    total: int
    page: int
    limit: int
