"""
Change Verification Model.

Tracks user feedback on change detection accuracy, enabling
false positive identification and suppression rule creation.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ChangeVerification(SQLModel, table=True):
    """
    Records user verification of detected changes.

    When users review changes flagged by the AI diff service, they can
    mark them as verified (true positive) or false positive. This feedback
    helps track accuracy and enables suppression rule creation.
    """

    __tablename__ = "change_verifications"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    change_diff_id: UUID = Field(foreign_key="change_diff.diff_id", index=True)
    verified_by: UUID = Field(foreign_key="users.id")
    is_false_positive: bool = Field(
        default=False, description="True if the detected change was not meaningful"
    )
    feedback_reason: Optional[str] = Field(
        default=None, max_length=500, description="User's explanation for the verification decision"
    )
    suppression_rule_id: Optional[UUID] = Field(
        default=None,
        foreign_key="suppression_rules.id",
        description="Link to suppression rule created from this feedback",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Optional[datetime] = Field(default=None)
