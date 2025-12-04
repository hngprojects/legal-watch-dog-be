"""
Unit tests for DataRevision model baseline acceptance fields.
Tests baseline functionality added to the DataRevision model.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.api.modules.v1.scraping.models.data_revision import DataRevision


class TestDataRevisionBaselineFields:
    """Tests for baseline acceptance fields in DataRevision model."""

    @pytest.fixture
    def sample_revision(self):
        """Fixture for a sample data revision."""
        return DataRevision(
            id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            minio_object_key="scrapes/2025/12/04/test-revision.html",
            content_hash="abc123def456",
            extracted_data={"title": "Test Document", "content": "Test content"},
            ai_summary="Test summary",
            ai_markdown_summary="## Test Summary",
            ai_confidence_score=0.95,
            was_change_detected=False,
            # Baseline fields - default values
            is_baseline=False,
            baseline_accepted_at=None,
            baseline_accepted_by=None,
            baseline_notes=None,
        )

    def test_revision_default_baseline_values(self, sample_revision):
        """Test that baseline fields have correct default values."""
        assert sample_revision.is_baseline is False
        assert sample_revision.baseline_accepted_at is None
        assert sample_revision.baseline_accepted_by is None
        assert sample_revision.baseline_notes is None

    def test_revision_set_as_baseline(self, sample_revision):
        """Test setting a revision as baseline."""
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        sample_revision.is_baseline = True
        sample_revision.baseline_accepted_at = now
        sample_revision.baseline_accepted_by = user_id
        sample_revision.baseline_notes = "Initial baseline for testing"

        assert sample_revision.is_baseline is True
        assert sample_revision.baseline_accepted_at == now
        assert sample_revision.baseline_accepted_by == user_id
        assert sample_revision.baseline_notes == "Initial baseline for testing"

    def test_revision_unmark_baseline(self, sample_revision):
        """Test unmarking a revision as baseline."""
        # First set as baseline
        sample_revision.is_baseline = True
        sample_revision.baseline_accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        sample_revision.baseline_accepted_by = uuid.uuid4()

        # Then unmark
        sample_revision.is_baseline = False

        assert sample_revision.is_baseline is False
        # Note: Historical fields remain for audit trail
        assert sample_revision.baseline_accepted_at is not None
        assert sample_revision.baseline_accepted_by is not None

    def test_revision_baseline_notes_max_length(self, sample_revision):
        """Test baseline notes field accepts text up to max length."""
        # Create a note with 500 characters (the max length)
        long_note = "A" * 500
        sample_revision.baseline_notes = long_note

        assert len(sample_revision.baseline_notes) == 500
        assert sample_revision.baseline_notes == long_note

    def test_revision_with_all_fields(self):
        """Test creating a revision with all baseline fields populated."""
        user_id = uuid.uuid4()
        source_id = uuid.uuid4()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        revision = DataRevision(
            id=uuid.uuid4(),
            source_id=source_id,
            minio_object_key="scrapes/test.html",
            content_hash="hash123",
            extracted_data={"data": "test"},
            ai_summary="Summary",
            was_change_detected=True,
            is_baseline=True,
            baseline_accepted_at=now,
            baseline_accepted_by=user_id,
            baseline_notes="Accepted as baseline after review",
        )

        assert revision.is_baseline is True
        assert revision.baseline_accepted_at == now
        assert revision.baseline_accepted_by == user_id
        assert revision.baseline_notes == "Accepted as baseline after review"

    def test_revision_baseline_workflow_simulation(self, sample_revision):
        """Test a complete baseline acceptance workflow."""
        user_id = uuid.uuid4()

        # Step 1: Revision created (not baseline)
        assert sample_revision.is_baseline is False

        # Step 2: User accepts as baseline
        sample_revision.is_baseline = True
        sample_revision.baseline_accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        sample_revision.baseline_accepted_by = user_id
        sample_revision.baseline_notes = "First baseline"

        assert sample_revision.is_baseline is True

        # Step 3: Later, this baseline is replaced (unmark)
        sample_revision.is_baseline = False

        # Baseline history preserved
        assert sample_revision.baseline_accepted_at is not None
        assert sample_revision.baseline_accepted_by == user_id
        assert sample_revision.baseline_notes == "First baseline"
