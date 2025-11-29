from typing import Optional

from pydantic import BaseModel, Field


class SuggestedSource(BaseModel):
    """Represents a validated source URL suggested by the AI researcher."""

    title: str
    url: str
    snippet: str
    confidence_reason: str
    is_official: bool


class SuggestionRequest(BaseModel):
    """Request model for source suggestion."""

    jurisdiction_description: str = Field(
        ..., description="The description of the jurisdiction (e.g., 'Minimum Wage Regulations')."
    )
    jurisdiction_name: Optional[str] = Field(
        None, description="Optional context or name of the jurisdiction (e.g., 'United Kingdom')."
    )
    project_description: str = Field(
        ...,
        description="User's monitoring goal (e.g., 'Official National Minimum Wage Rates').",
    )
