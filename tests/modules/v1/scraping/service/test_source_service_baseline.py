"""
Unit tests for SourceService baseline management methods.
Tests accept_revision_as_baseline, get_current_baseline, and get_baseline_history.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.schemas.baseline_schema import BaselineAcceptanceRequest
from app.api.modules.v1.scraping.service.source_service import SourceService


class TestSourceServiceBaseline:
    """Tests for SourceService baseline functionality."""

    @pytest.fixture
    def sample_source_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sample_user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sample_revision(self, sample_source_id):
        return DataRevision(
            id=uuid.uuid4(),
            source_id=sample_source_id,
            minio_object_key="test.html",
            was_change_detected=True,
            is_baseline=False,
        )

    @pytest.mark.asyncio
    async def test_accept_revision_as_baseline_success(self, sample_revision, sample_user_id):
        """Test successfully accepting a revision as baseline."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        acceptance_data = BaselineAcceptanceRequest(notes="Looks good")

        # Mock getting the revision
        mock_db.get = AsyncMock(return_value=sample_revision)

        # Mock finding existing baselines (empty list)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.accept_revision_as_baseline(
            mock_db, sample_revision.id, acceptance_data, sample_user_id
        )

        assert result.is_baseline is True
        assert result.baseline_accepted_by == sample_user_id
        assert result.baseline_notes == "Looks good"
        assert result.baseline_accepted_at is not None

        # Verify DB interactions
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_accept_revision_replaces_old_baseline(self, sample_revision, sample_user_id):
        """Test that accepting a new baseline unsets the old one."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        acceptance_data = BaselineAcceptanceRequest(notes="New baseline")

        # Old baseline
        old_baseline = DataRevision(
            id=uuid.uuid4(),
            source_id=sample_revision.source_id,
            minio_object_key="old.html",
            is_baseline=True,
        )

        mock_db.get = AsyncMock(return_value=sample_revision)

        # Mock finding existing baseline
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [old_baseline]
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await service.accept_revision_as_baseline(
            mock_db, sample_revision.id, acceptance_data, sample_user_id
        )

        # Verify old baseline was unset
        assert old_baseline.is_baseline is False

        # Verify new baseline was set
        assert sample_revision.is_baseline is True

        # Verify both were added to session
        assert mock_db.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_accept_revision_not_found(self, sample_user_id):
        """Test error when revision doesn't exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await service.accept_revision_as_baseline(
                mock_db, uuid.uuid4(), BaselineAcceptanceRequest(), sample_user_id
            )

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_current_baseline_found(self, sample_source_id):
        """Test retrieving an existing baseline."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        baseline = DataRevision(
            id=uuid.uuid4(),
            source_id=sample_source_id,
            minio_object_key="baseline.html",
            is_baseline=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = baseline
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_current_baseline(mock_db, sample_source_id)

        assert result == baseline
        assert result.is_baseline is True

    @pytest.mark.asyncio
    async def test_get_current_baseline_none(self, sample_source_id):
        """Test retrieving baseline when none exists."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_current_baseline(mock_db, sample_source_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_baseline_history_success(self, sample_source_id):
        """Test retrieving baseline history."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        # Mock source exists
        mock_db.get = AsyncMock(return_value=Source(id=sample_source_id))

        history = [
            DataRevision(id=uuid.uuid4(), baseline_accepted_at=datetime.now()),
            DataRevision(id=uuid.uuid4(), baseline_accepted_at=datetime.now()),
        ]

        # Mock history query
        mock_result_history = MagicMock()
        mock_result_history.scalars.return_value.all.return_value = history

        # Mock count query
        mock_result_count = MagicMock()
        mock_result_count.scalar_one.return_value = 2

        mock_db.execute = AsyncMock(side_effect=[mock_result_history, mock_result_count])

        results, total = await service.get_baseline_history(mock_db, sample_source_id)

        assert len(results) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_baseline_history_source_not_found(self):
        """Test history retrieval for non-existent source."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await service.get_baseline_history(mock_db, uuid.uuid4())

        assert exc.value.status_code == 404
