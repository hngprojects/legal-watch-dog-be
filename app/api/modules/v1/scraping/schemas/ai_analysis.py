from typing import Any, Dict

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """
    Schema for the Extraction phase (Text -> JSON).
    The AI populates 'extracted_data' with keys derived from the prompt logic.
    """

    summary: str = Field(..., description="A concise summary.")

    markdown_summary: str = Field(
        default="",
        description="Markdown-formatted summary with extracted data "
        "presented as formatted table or list. Generated after extraction.",
    )

    confidence_score: float = Field(..., description="0.0 to 1.0 confidence score.", ge=0.0, le=1.0)

    extracted_data: Dict[str, Any] = Field(..., description="Key-value facts.")

    class Config:
        extra = "forbid"
