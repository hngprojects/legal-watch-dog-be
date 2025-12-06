"""
Schemas for Change Verification and False Positive Management.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.modules.v1.scraping.models.suppression_rule import SuppressionRuleType


class SuppressionRuleCreate(BaseModel):
    """Request schema for creating a suppression rule."""

    rule_type: SuppressionRuleType
    rule_pattern: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Pattern to match (JSON path, regex, or field name)",
    )
    rule_description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable explanation of what this rule suppresses",
    )


class ChangeVerificationRequest(BaseModel):
    """Request schema for verifying a detected change."""

    is_false_positive: bool = Field(
        ..., description="True if the detected change was not meaningful"
    )
    feedback_reason: Optional[str] = Field(
        None, max_length=500, description="Explanation for the verification decision"
    )
    create_suppression_rule: bool = Field(
        default=False, description="Whether to create a suppression rule from this feedback"
    )
    suppression_rule: Optional[SuppressionRuleCreate] = Field(
        None, description="Suppression rule details if create_suppression_rule is True"
    )


class ChangeVerificationUpdate(BaseModel):
    """Request schema for updating an existing verification."""

    is_false_positive: Optional[bool] = None
    feedback_reason: Optional[str] = Field(None, max_length=500)


class ChangeVerificationResponse(BaseModel):
    """Response schema for change verification data."""

    id: UUID
    change_diff_id: UUID
    verified_by: UUID
    is_false_positive: bool
    feedback_reason: Optional[str]
    suppression_rule_id: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class SuppressionRuleUpdate(BaseModel):
    """Request schema for updating a suppression rule."""

    rule_pattern: Optional[str] = Field(None, min_length=1, max_length=500)
    rule_description: Optional[str] = Field(None, min_length=1, max_length=500)
    is_active: Optional[bool] = None


class SuppressionRuleResponse(BaseModel):
    """Response schema for suppression rule data."""

    id: UUID
    source_id: UUID
    rule_type: SuppressionRuleType
    rule_pattern: str
    rule_description: str
    created_by: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class FalsePositiveMetrics(BaseModel):
    """Response schema for false positive rate metrics."""

    source_id: UUID
    total_changes: int = Field(description="Total changes detected in the period")
    verified_changes: int = Field(description="Changes that were verified by users")
    false_positives: int = Field(description="Changes marked as false positives")
    false_positive_rate: float = Field(
        description="Percentage of verified changes that were false positives"
    )
    period_days: int = Field(description="Number of days included in the metrics")
