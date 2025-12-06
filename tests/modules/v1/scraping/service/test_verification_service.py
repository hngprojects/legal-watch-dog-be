"""
Unit tests for VerificationService.

Tests change verification, suppression rule management, and metrics calculation.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.change_verification import ChangeVerification
from app.api.modules.v1.scraping.models.suppression_rule import (
    SuppressionRule,
    SuppressionRuleType,
)
from app.api.modules.v1.scraping.schemas.verification_schema import (
    ChangeVerificationRequest,
    ChangeVerificationUpdate,
    SuppressionRuleCreate,
    SuppressionRuleUpdate,
)
from app.api.modules.v1.scraping.service.verification_service import VerificationService


class TestVerificationServiceChangeVerification:
    """Tests for change verification operations."""

    @pytest.fixture
    def service(self):
        return VerificationService()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def sample_diff_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sample_user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sample_source_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_verify_change_success(
        self, service, mock_db, sample_diff_id, sample_user_id, sample_source_id
    ):
        """Test successful change verification."""
        mock_diff = ChangeDiff(
            diff_id=sample_diff_id,
            new_revision_id=uuid.uuid4(),
            old_revision_id=uuid.uuid4(),
        )

        # Mock the database queries
        mock_db.execute.side_effect = [
            # First call - check diff exists
            MagicMock(scalars=lambda: MagicMock(first=lambda: mock_diff)),
            # Second call - check existing verification
            MagicMock(scalars=lambda: MagicMock(first=lambda: None)),
        ]

        request = ChangeVerificationRequest(
            is_false_positive=True,
            feedback_reason="This is a timestamp change",
        )

        await service.verify_change(
            mock_db, sample_diff_id, request, sample_user_id
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_change_diff_not_found(
        self, service, mock_db, sample_diff_id, sample_user_id
    ):
        """Test verification fails when diff not found."""
        mock_db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(first=lambda: None)
        )

        request = ChangeVerificationRequest(is_false_positive=False)

        with pytest.raises(HTTPException) as exc_info:
            await service.verify_change(mock_db, sample_diff_id, request, sample_user_id)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_change_already_verified(
        self, service, mock_db, sample_diff_id, sample_user_id
    ):
        """Test verification fails when change already verified."""
        mock_diff = ChangeDiff(diff_id=sample_diff_id)
        existing_verification = ChangeVerification(
            id=uuid.uuid4(),
            change_diff_id=sample_diff_id,
            verified_by=sample_user_id,
        )

        mock_db.execute.side_effect = [
            MagicMock(scalars=lambda: MagicMock(first=lambda: mock_diff)),
            MagicMock(scalars=lambda: MagicMock(first=lambda: existing_verification)),
        ]

        request = ChangeVerificationRequest(is_false_positive=False)

        with pytest.raises(HTTPException) as exc_info:
            await service.verify_change(mock_db, sample_diff_id, request, sample_user_id)

        assert exc_info.value.status_code == 409
        assert "already been verified" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_verification_success(
        self, service, mock_db, sample_user_id
    ):
        """Test successful verification update."""
        verification_id = uuid.uuid4()
        verification = ChangeVerification(
            id=verification_id,
            change_diff_id=uuid.uuid4(),
            verified_by=sample_user_id,
            is_false_positive=False,
        )

        mock_db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(first=lambda: verification)
        )

        update = ChangeVerificationUpdate(
            is_false_positive=True,
            feedback_reason="Changed my mind",
        )

        await service.update_verification(
            mock_db, verification_id, update, sample_user_id
        )

        assert verification.is_false_positive is True
        assert verification.feedback_reason == "Changed my mind"
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_update_verification_not_owner(
        self, service, mock_db, sample_user_id
    ):
        """Test update fails when user is not the original verifier."""
        verification_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        verification = ChangeVerification(
            id=verification_id,
            change_diff_id=uuid.uuid4(),
            verified_by=other_user_id,  # Different user
        )

        mock_db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(first=lambda: verification)
        )

        update = ChangeVerificationUpdate(is_false_positive=True)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_verification(
                mock_db, verification_id, update, sample_user_id
            )

        assert exc_info.value.status_code == 403


class TestVerificationServiceSuppressionRules:
    """Tests for suppression rule operations."""

    @pytest.fixture
    def service(self):
        return VerificationService()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def sample_source_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sample_user_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_suppression_rule_success(
        self, service, mock_db, sample_source_id, sample_user_id
    ):
        """Test successful suppression rule creation."""
        rule_data = SuppressionRuleCreate(
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="last_modified",
            rule_description="Ignore timestamp changes",
        )

        await service.create_suppression_rule(
            mock_db, sample_source_id, rule_data, sample_user_id
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_suppression_rule_invalid_regex(
        self, service, mock_db, sample_source_id, sample_user_id
    ):
        """Test creation fails with invalid regex pattern."""
        rule_data = SuppressionRuleCreate(
            rule_type=SuppressionRuleType.REGEX,
            rule_pattern="[invalid(regex",  # Invalid regex
            rule_description="Bad pattern",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_suppression_rule(
                mock_db, sample_source_id, rule_data, sample_user_id
            )

        assert exc_info.value.status_code == 400
        assert "Invalid regex" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_suppression_rule_success(
        self, service, mock_db, sample_user_id
    ):
        """Test successful suppression rule update."""
        rule_id = uuid.uuid4()
        rule = SuppressionRule(
            id=rule_id,
            source_id=uuid.uuid4(),
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="old_field",
            rule_description="Old description",
            created_by=sample_user_id,
        )

        mock_db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(first=lambda: rule)
        )

        update = SuppressionRuleUpdate(
            rule_pattern="new_field",
            rule_description="New description",
            is_active=False,
        )

        await service.update_suppression_rule(
            mock_db, rule_id, update, sample_user_id
        )

        assert rule.rule_pattern == "new_field"
        assert rule.rule_description == "New description"
        assert rule.is_active is False
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_delete_suppression_rule_success(
        self, service, mock_db, sample_user_id
    ):
        """Test successful suppression rule deletion."""
        rule_id = uuid.uuid4()
        rule = SuppressionRule(
            id=rule_id,
            source_id=uuid.uuid4(),
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="field",
            rule_description="Description",
            created_by=sample_user_id,
        )

        mock_db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(first=lambda: rule)
        )

        result = await service.delete_suppression_rule(mock_db, rule_id, sample_user_id)

        assert result is True
        assert mock_db.delete.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_delete_suppression_rule_not_found(
        self, service, mock_db, sample_user_id
    ):
        """Test deletion fails when rule not found."""
        rule_id = uuid.uuid4()

        mock_db.execute.return_value = MagicMock(
            scalars=lambda: MagicMock(first=lambda: None)
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_suppression_rule(mock_db, rule_id, sample_user_id)

        assert exc_info.value.status_code == 404


class TestVerificationServiceRuleApplication:
    """Tests for suppression rule application logic."""

    @pytest.fixture
    def service(self):
        return VerificationService()

    def test_apply_suppression_rules_field_name(self, service):
        """Test field name suppression rule."""
        rules = [
            SuppressionRule(
                id=uuid.uuid4(),
                source_id=uuid.uuid4(),
                rule_type=SuppressionRuleType.FIELD_NAME,
                rule_pattern="last_modified",
                rule_description="Ignore timestamp",
                created_by=uuid.uuid4(),
            )
        ]

        diff_data = {
            "changes": [
                {"field": "last_modified", "old_value": "2024-01-01", "new_value": "2024-01-02"},
                {"field": "content", "old_value": "old", "new_value": "new"},
            ]
        }

        result = service.apply_suppression_rules(rules, diff_data)

        assert len(result["changes"]) == 1
        assert result["changes"][0]["field"] == "content"
        assert result["suppressed_count"] == 1

    def test_apply_suppression_rules_regex(self, service):
        """Test regex suppression rule."""
        rules = [
            SuppressionRule(
                id=uuid.uuid4(),
                source_id=uuid.uuid4(),
                rule_type=SuppressionRuleType.REGEX,
                rule_pattern=r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                rule_description="Ignore ISO timestamps",
                created_by=uuid.uuid4(),
            )
        ]

        diff_data = {
            "changes": [
                {
                    "field": "date",
                    "old_value": "2024-01-01T10:00:00",
                    "new_value": "2024-01-02T11:00:00",
                },
                {
                    "field": "content",
                    "old_value": "old text",
                    "new_value": "new text",
                },
            ]
        }

        result = service.apply_suppression_rules(rules, diff_data)

        assert len(result["changes"]) == 1
        assert result["changes"][0]["field"] == "content"

    def test_apply_suppression_rules_json_path(self, service):
        """Test JSON path suppression rule."""
        rules = [
            SuppressionRule(
                id=uuid.uuid4(),
                source_id=uuid.uuid4(),
                rule_type=SuppressionRuleType.JSON_PATH,
                rule_pattern="$.metadata",
                rule_description="Ignore metadata changes",
                created_by=uuid.uuid4(),
            )
        ]

        diff_data = {
            "changes": [
                {"path": "$.metadata.version", "old_value": "1.0", "new_value": "1.1"},
                {"path": "$.content.title", "old_value": "Old", "new_value": "New"},
            ]
        }

        result = service.apply_suppression_rules(rules, diff_data)

        assert len(result["changes"]) == 1
        assert result["changes"][0]["path"] == "$.content.title"

    def test_apply_suppression_rules_empty_rules(self, service):
        """Test with no rules returns original data."""
        diff_data = {"changes": [{"field": "test", "old_value": "a", "new_value": "b"}]}

        result = service.apply_suppression_rules([], diff_data)

        assert result == diff_data

    def test_apply_suppression_rules_empty_diff(self, service):
        """Test with empty diff data returns empty."""
        rules = [
            SuppressionRule(
                id=uuid.uuid4(),
                source_id=uuid.uuid4(),
                rule_type=SuppressionRuleType.FIELD_NAME,
                rule_pattern="test",
                rule_description="Test",
                created_by=uuid.uuid4(),
            )
        ]

        result = service.apply_suppression_rules(rules, {})

        assert result == {}
