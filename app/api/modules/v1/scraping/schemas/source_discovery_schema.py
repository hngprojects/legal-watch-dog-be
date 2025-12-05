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
    """Request model for source suggestion.

    Acts as a search query wrapper where jurisdiction provides the scope/boundary,
    and the search_query (optional) allows specific targeting.
    """

    jurisdiction_description: str = Field(
        ...,
        description="The scope or description of the jurisdiction "
        "(e.g., 'Central Bank of Nigeria Regulations').",
    )
    jurisdiction_name: Optional[str] = Field(
        None, description="Optional name of the jurisdiction (e.g., 'Nigeria')."
    )
    jurisdiction_prompt: Optional[str] = Field(
        None,
        description="Optional AI prompt that guides extraction, summarization, "
        "or classification tasks for this jurisdiction (e.g., 'Focus on crypto "
        "asset guidelines and licensing requirements').",
    )
    project_description: str = Field(
        ...,
        description="The broader project goal (e.g., 'Monitor Crypto Asset Guidelines').",
    )
    search_query: Optional[str] = Field(
        None,
        description="Specific user input to narrow the search "
        "(e.g., '2024 crypto licensing requirements').",
    )
