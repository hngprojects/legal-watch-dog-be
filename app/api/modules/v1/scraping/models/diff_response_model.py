from typing import Optional

from pydantic import BaseModel, Field


class DiffResult(BaseModel):
    """
    Structured output for the semantic difference check.
    """

    detected: bool = Field(
        ...,
        description="True if a meaningful change occurred relevant to the context, "
        "False otherwise.",
    )
    change_summary: str = Field(
        ...,
        description="A concise, human-readable summary of exactly what changed"
        " (e.g., 'Price increased from $10 to $12').",
    )
    confidence_score: float = Field(
        ...,
        description="A score between 0.0 and 1.0 indicating"
        " how confident the AI is in this judgment.",
    )
    change_type: Optional[str] = Field(
        None,
        description="Category of change: 'Critical',"
        " 'Minor', 'Cosmetic', or 'New Record'.",
    )
