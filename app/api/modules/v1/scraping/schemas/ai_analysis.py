from pydantic import BaseModel, Field


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

    class Config:
        extra = "forbid"
