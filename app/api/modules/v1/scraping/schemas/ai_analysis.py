from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


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


class ChangeDetectionResult(BaseModel):
    """
    Strict schema for the Semantic Diff phase (JSON A vs JSON B).
    """

    has_changed: bool = Field(
        ...,
        description="True if FACTUAL information changed. False if only phrasing changed.",
    )

    change_summary: str = Field(
        ...,
        description="One sentence explaining exactly what changed"
        " (e.g. 'Visa price increased from 60 to 80').",
    )

    risk_level: str = Field(
        ..., description="LOW, MEDIUM, or HIGH based on the severity of the change."
    )

    model_config = ConfigDict(extra="forbid")
