"""
Unit tests for ChangeVerification model.
Tests user feedback tracking for detected changes.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.api.modules.v1.scraping.models.change_verification import ChangeVerification


class TestChangeVerificationModel:
    """Tests for ChangeVerification model."""

    @pytest.fixture
    def sample_verification(self):
        """Fixture for a sample change verification."""
        return ChangeVerification(
            id=uuid.uuid4(),
            change_diff_id=uuid.uuid4(),
            verified_by=uuid.uuid4(),
            is_false_positive=False,
            feedback_reason="Change is legitimate - new regulation published",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    def test_verification_creation_with_defaults(self):
        """Test creating a verification with default values."""
        change_diff_id = uuid.uuid4()
        user_id = uuid.uuid4()

        verification = ChangeVerification(
            change_diff_id=change_diff_id,
            verified_by=user_id,
            is_false_positive=True,
        )

        assert verification.id is not None
        assert verification.change_diff_id == change_diff_id
        assert verification.verified_by == user_id
        assert verification.is_false_positive is True
        assert verification.feedback_reason is None
        assert verification.suppression_rule_id is None
        assert verification.created_at is not None
        assert verification.updated_at is None

    def test_verification_true_positive(self, sample_verification):
        """Test marking a change as a true positive."""
        assert sample_verification.is_false_positive is False
        assert "legitimate" in sample_verification.feedback_reason

    def test_verification_false_positive(self):
        """Test marking a change as a false positive."""
        verification = ChangeVerification(
            change_diff_id=uuid.uuid4(),
            verified_by=uuid.uuid4(),
            is_false_positive=True,
            feedback_reason="Just timestamp changed, not actual content",
        )

        assert verification.is_false_positive is True
        assert "timestamp" in verification.feedback_reason

    def test_verification_with_suppression_rule(self):
        """Test verification linked to a suppression rule."""
        suppression_rule_id = uuid.uuid4()

        verification = ChangeVerification(
            change_diff_id=uuid.uuid4(),
            verified_by=uuid.uuid4(),
            is_false_positive=True,
            feedback_reason="Metadata changes should be ignored",
            suppression_rule_id=suppression_rule_id,
        )

        assert verification.is_false_positive is True
        assert verification.suppression_rule_id == suppression_rule_id

    def test_verification_feedback_reason_max_length(self):
        """Test feedback reason field accepts text up to 500 characters."""
        long_reason = "A" * 500
        verification = ChangeVerification(
            change_diff_id=uuid.uuid4(),
            verified_by=uuid.uuid4(),
            is_false_positive=True,
            feedback_reason=long_reason,
        )

        assert len(verification.feedback_reason) == 500

    def test_verification_update_workflow(self, sample_verification):
        """Test updating a verification (e.g., correcting a mistake)."""
        # Initially marked as true positive
        assert sample_verification.is_false_positive is False

        # User realizes it was a false positive
        sample_verification.is_false_positive = True
        sample_verification.feedback_reason = "Corrected: This was just a version number change"
        sample_verification.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        assert sample_verification.is_false_positive is True
        assert "Corrected" in sample_verification.feedback_reason
        assert sample_verification.updated_at is not None

    def test_verification_minimal_creation(self):
        """Test creating verification with minimal required fields."""
        verification = ChangeVerification(
            change_diff_id=uuid.uuid4(),
            verified_by=uuid.uuid4(),
            is_false_positive=False,
        )

        assert verification.id is not None
        assert verification.created_at is not None
        assert verification.feedback_reason is None


class TestChangeVerificationWorkflow:
    """Test realistic verification workflows."""

    def test_false_positive_detection_workflow(self):
        """Test complete false positive detection and verification workflow."""
        change_diff_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Step 1: Create initial verification
        verification = ChangeVerification(
            change_diff_id=change_diff_id,
            verified_by=user_id,
            is_false_positive=True,
            feedback_reason="Only metadata timestamp changed",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        assert verification.is_false_positive is True
        assert verification.suppression_rule_id is None

        # Step 2: User creates suppression rule and links it
        suppression_rule_id = uuid.uuid4()
        verification.suppression_rule_id = suppression_rule_id
        verification.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        assert verification.suppression_rule_id == suppression_rule_id
        assert verification.updated_at is not None

    def test_verification_audit_trail(self):
        """Test that verifications maintain an audit trail."""
        created_time = datetime(2025, 12, 4, 10, 0, 0)
        updated_time = datetime(2025, 12, 4, 11, 0, 0)

        verification = ChangeVerification(
            change_diff_id=uuid.uuid4(),
            verified_by=uuid.uuid4(),
            is_false_positive=False,
            feedback_reason="Initial verification - looks good",
            created_at=created_time,
        )

        # Later, user updates their assessment
        verification.is_false_positive = True
        verification.feedback_reason = "Actually a false positive on closer inspection"
        verification.updated_at = updated_time

        # Audit trail preserved
        assert verification.created_at == created_time
        assert verification.updated_at == updated_time
        assert verification.updated_at > verification.created_at
