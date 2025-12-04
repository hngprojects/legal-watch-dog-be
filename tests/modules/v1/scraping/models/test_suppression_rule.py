"""
Unit tests for SuppressionRule model.
Tests suppression rule creation and configuration.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.api.modules.v1.scraping.models.suppression_rule import (
    SuppressionRule,
    SuppressionRuleType,
)


class TestSuppressionRuleModel:
    """Tests for SuppressionRule model."""

    @pytest.fixture
    def sample_source_id(self):
        """Fixture for a sample source UUID."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_user_id(self):
        """Fixture for a sample user UUID."""
        return uuid.uuid4()

    def test_rule_creation_field_name_type(self, sample_source_id, sample_user_id):
        """Test creating a FIELD_NAME suppression rule."""
        rule = SuppressionRule(
            id=uuid.uuid4(),
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="last_updated",
            rule_description="Ignore timestamp field changes",
            created_by=sample_user_id,
            is_active=True,
        )

        assert rule.rule_type == SuppressionRuleType.FIELD_NAME
        assert rule.rule_pattern == "last_updated"
        assert rule.is_active is True

    def test_rule_creation_json_path_type(self, sample_source_id, sample_user_id):
        """Test creating a JSON_PATH suppression rule."""
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.JSON_PATH,
            rule_pattern="$.metadata.scrape_timestamp",
            rule_description="Ignore metadata timestamp changes",
            created_by=sample_user_id,
        )

        assert rule.rule_type == SuppressionRuleType.JSON_PATH
        assert rule.rule_pattern == "$.metadata.scrape_timestamp"
        assert rule.id is not None  # Auto-generated
        assert rule.is_active is True  # Default value
        assert rule.created_at is not None

    def test_rule_creation_regex_type(self, sample_source_id, sample_user_id):
        """Test creating a REGEX suppression rule."""
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.REGEX,
            rule_pattern=r"Version \d+\.\d+\.\d+",
            rule_description="Ignore version number changes",
            created_by=sample_user_id,
        )

        assert rule.rule_type == SuppressionRuleType.REGEX
        assert rule.rule_pattern == r"Version \d+\.\d+\.\d+"
        assert "version number" in rule.rule_description.lower()

    def test_rule_default_active_state(self, sample_source_id, sample_user_id):
        """Test that rules are active by default."""
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="test_field",
            rule_description="Test rule",
            created_by=sample_user_id,
        )

        assert rule.is_active is True

    def test_rule_can_be_created_inactive(self, sample_source_id, sample_user_id):
        """Test creating an inactive rule."""
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="test_field",
            rule_description="Test rule",
            created_by=sample_user_id,
            is_active=False,
        )

        assert rule.is_active is False

    def test_rule_deactivation(self, sample_source_id, sample_user_id):
        """Test deactivating an active rule."""
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="test_field",
            rule_description="Test rule",
            created_by=sample_user_id,
            is_active=True,
        )

        assert rule.is_active is True

        # Deactivate the rule
        rule.is_active = False
        rule.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        assert rule.is_active is False
        assert rule.updated_at is not None

    def test_rule_pattern_max_length(self, sample_source_id, sample_user_id):
        """Test rule pattern field accepts text up to 500 characters."""
        long_pattern = "A" * 500
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern=long_pattern,
            rule_description="Test long pattern",
            created_by=sample_user_id,
        )

        assert len(rule.rule_pattern) == 500

    def test_rule_description_max_length(self, sample_source_id, sample_user_id):
        """Test rule description field accepts text up to 500 characters."""
        long_description = "B" * 500
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="test",
            rule_description=long_description,
            created_by=sample_user_id,
        )

        assert len(rule.rule_description) == 500

    def test_rule_update_workflow(self, sample_source_id, sample_user_id):
        """Test updating a rule's pattern and description."""
        rule = SuppressionRule(
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="old_field",
            rule_description="Old description",
            created_by=sample_user_id,
            created_at=datetime(2025, 12, 1, 10, 0, 0),
        )

        # Update the rule
        rule.rule_pattern = "new_field"
        rule.rule_description = "Updated description"
        rule.updated_at = datetime(2025, 12, 4, 12, 0, 0)

        assert rule.rule_pattern == "new_field"
        assert rule.rule_description == "Updated description"
        assert rule.updated_at is not None
        assert rule.updated_at > rule.created_at


class TestSuppressionRuleTypes:
    """Test the three types of suppression rules."""

    def test_all_rule_types_exist(self):
        """Test that all three rule types are defined."""
        assert hasattr(SuppressionRuleType, "FIELD_NAME")
        assert hasattr(SuppressionRuleType, "JSON_PATH")
        assert hasattr(SuppressionRuleType, "REGEX")

    def test_rule_type_values(self):
        """Test rule type enum values."""
        assert SuppressionRuleType.FIELD_NAME.value == "FIELD_NAME"
        assert SuppressionRuleType.JSON_PATH.value == "JSON_PATH"
        assert SuppressionRuleType.REGEX.value == "REGEX"


class TestSuppressionRuleWorkflow:
    """Test realistic suppression rule workflows."""

    def test_complete_suppression_workflow(self):
        """Test creating, updating, and deactivating a suppression rule."""
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Step 1: User identifies a false positive
        # Step 2: User creates suppression rule
        rule = SuppressionRule(
            source_id=source_id,
            rule_type=SuppressionRuleType.JSON_PATH,
            rule_pattern="$.metadata.last_updated",
            rule_description="Ignore metadata timestamp updates",
            created_by=user_id,
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        assert rule.is_active is True

        # Step 3: Rule is applied in future scrapes
        # (simulated by the fact that it exists and is active)

        # Step 4: Later, user refines the rule
        rule.rule_pattern = "$.metadata"  # Broader pattern
        rule.rule_description = "Ignore all metadata changes"
        rule.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        assert rule.rule_pattern == "$.metadata"
        assert rule.updated_at is not None

        # Step 5: Much later, rule is no longer needed
        rule.is_active = False

        assert rule.is_active is False

    def test_multiple_rules_for_same_source(self):
        """Test that a source can have multiple suppression rules."""
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        rule1 = SuppressionRule(
            source_id=source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="last_updated",
            rule_description="Ignore timestamp",
            created_by=user_id,
        )

        rule2 = SuppressionRule(
            source_id=source_id,
            rule_type=SuppressionRuleType.REGEX,
            rule_pattern=r"Version \d+",
            rule_description="Ignore version numbers",
            created_by=user_id,
        )

        rule3 = SuppressionRule(
            source_id=source_id,
            rule_type=SuppressionRuleType.JSON_PATH,
            rule_pattern="$.metadata",
            rule_description="Ignore metadata",
            created_by=user_id,
        )

        # All rules belong to the same source
        assert rule1.source_id == source_id
        assert rule2.source_id == source_id
        assert rule3.source_id == source_id

        # But have different patterns and types
        assert rule1.rule_type != rule2.rule_type
        assert rule2.rule_type != rule3.rule_type
        assert len({rule1.rule_pattern, rule2.rule_pattern, rule3.rule_pattern}) == 3
