"""
Unit tests for Source baseline API endpoints.

Tests the endpoint functions directly without requiring a full HTTP client.
This approach is simpler and faster than full integration testing.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.schemas.baseline_schema import (
    BaselineAcceptanceRequest,
    BaselineHistoryResponse,
)
from app.api.modules.v1.users.models.users_model import User


class TestBaselineEndpoints:
    """Tests for baseline endpoint functions."""

    @pytest.fixture
    def sample_source_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def sample_revision_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_user(self):
        return User(id=uuid.uuid4(), email="test@example.com", is_active=True)

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_accept_baseline_calls_service(
        self, mock_db, mock_user, sample_revision_id, sample_source_id
    ):
        """Test that accept_baseline endpoint calls the service correctly."""
        from app.api.modules.v1.scraping.routes.source_routes import accept_baseline

        mock_revision = DataRevision(
            id=sample_revision_id,
            source_id=sample_source_id,
            is_baseline=True,
            baseline_accepted_at=datetime.now(),
            baseline_accepted_by=mock_user.id,
            baseline_notes="Test note",
            minio_object_key="test.html",
            scraped_at=datetime.now(),
            was_change_detected=False,
        )

        with patch("app.api.modules.v1.scraping.routes.source_routes.SourceService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.accept_revision_as_baseline.return_value = mock_revision
            MockService.return_value = mock_service_instance

            request = BaselineAcceptanceRequest(notes="Test note")
            result = await accept_baseline(
                revision_id=sample_revision_id,
                request=request,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.accept_revision_as_baseline.assert_awaited_once_with(
                mock_db, sample_revision_id, request, mock_user.id
            )
            assert result == mock_revision

    @pytest.mark.asyncio
    async def test_get_source_baseline_returns_revision(
        self, mock_db, mock_user, sample_source_id, sample_revision_id
    ):
        """Test that get_source_baseline returns the current baseline."""
        from app.api.modules.v1.scraping.routes.source_routes import get_source_baseline

        mock_revision = DataRevision(
            id=sample_revision_id,
            source_id=sample_source_id,
            is_baseline=True,
            minio_object_key="test.html",
            scraped_at=datetime.now(),
            was_change_detected=False,
        )

        with patch("app.api.modules.v1.scraping.routes.source_routes.SourceService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_current_baseline.return_value = mock_revision
            MockService.return_value = mock_service_instance

            result = await get_source_baseline(
                source_id=sample_source_id, db=mock_db, current_user=mock_user
            )

            mock_service_instance.get_current_baseline.assert_awaited_once_with(
                mock_db, sample_source_id
            )
            assert result == mock_revision

    @pytest.mark.asyncio
    async def test_get_source_baseline_returns_none(self, mock_db, mock_user, sample_source_id):
        """Test that get_source_baseline returns None when no baseline exists."""
        from app.api.modules.v1.scraping.routes.source_routes import get_source_baseline

        with patch("app.api.modules.v1.scraping.routes.source_routes.SourceService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_current_baseline.return_value = None
            MockService.return_value = mock_service_instance

            result = await get_source_baseline(
                source_id=sample_source_id, db=mock_db, current_user=mock_user
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_baseline_history_returns_paginated_response(
        self, mock_db, mock_user, sample_source_id
    ):
        """Test that get_baseline_history returns paginated history."""
        from app.api.modules.v1.scraping.routes.source_routes import get_baseline_history

        history = [
            DataRevision(
                id=uuid.uuid4(),
                source_id=sample_source_id,
                baseline_accepted_at=datetime.now(),
                minio_object_key="1.html",
                scraped_at=datetime.now(),
                was_change_detected=False,
            ),
            DataRevision(
                id=uuid.uuid4(),
                source_id=sample_source_id,
                baseline_accepted_at=datetime.now(),
                minio_object_key="2.html",
                scraped_at=datetime.now(),
                was_change_detected=False,
            ),
        ]

        with patch("app.api.modules.v1.scraping.routes.source_routes.SourceService") as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_baseline_history.return_value = (history, 2)
            MockService.return_value = mock_service_instance

            result = await get_baseline_history(
                source_id=sample_source_id,
                skip=0,
                limit=50,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.get_baseline_history.assert_awaited_once_with(
                mock_db, sample_source_id, 0, 50
            )
            assert isinstance(result, BaselineHistoryResponse)
            assert result.total == 2
            assert len(result.revisions) == 2
            assert result.page == 1
            assert result.limit == 50
