"""
Suppression Rule Model.

Defines rules for filtering out non-meaningful changes during
diff analysis to reduce false positives.
"""

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SuppressionRuleType(str, enum.Enum):
    """Types of suppression rules for filtering changes."""

    JSON_PATH = "JSON_PATH"  # Suppress changes to specific JSON paths
    REGEX = "REGEX"          # Suppress content matching regex patterns
    FIELD_NAME = "FIELD_NAME"  # Suppress changes to specific top-level fields


class SuppressionRule(SQLModel, table=True):
    """
    Defines patterns for suppressing non-meaningful changes.

    Suppression rules are applied before AI diff analysis to filter out
    known false positives like timestamps, metadata, or cosmetic changes.
    """

    __tablename__ = "suppression_rules"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="sources.id", index=True)
    rule_type: SuppressionRuleType = Field(
        description="Type of pattern matching to apply"
    )
    rule_pattern: str = Field(
        max_length=500,
        description="Pattern to match (JSON path, regex, or field name)"
    )
    rule_description: str = Field(
        max_length=500,
        description="Human-readable explanation of what this rule suppresses"
    )
    created_by: UUID = Field(foreign_key="users.id")
    is_active: bool = Field(
        default=True,
        description="Whether this rule is currently being applied"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Optional[datetime] = Field(default=None)
