"""
Unit tests for verification and suppression rule API endpoints.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.api.modules.v1.scraping.models.change_verification import ChangeVerification
from app.api.modules.v1.scraping.models.suppression_rule import (
    SuppressionRule,
    SuppressionRuleType,
)
from app.api.modules.v1.scraping.schemas.verification_schema import (
    ChangeVerificationRequest,
    ChangeVerificationUpdate,
    FalsePositiveMetrics,
    SuppressionRuleCreate,
)
from app.api.modules.v1.users.models.users_model import User


class TestVerificationEndpoints:
    """Tests for verification API endpoints."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        return User(id=uuid.uuid4(), email="test@example.com", is_active=True)

    @pytest.mark.asyncio
    async def test_verify_change_endpoint(self, mock_db, mock_user):
        """Test POST /changes/{diff_id}/verify endpoint."""
        from app.api.modules.v1.scraping.routes.source_routes import verify_change

        diff_id = uuid.uuid4()
        mock_verification = ChangeVerification(
            id=uuid.uuid4(),
            change_diff_id=diff_id,
            verified_by=mock_user.id,
            is_false_positive=True,
            feedback_reason="Test reason",
            created_at=datetime.now(),
        )

        with patch(
            "app.api.modules.v1.scraping.routes.source_routes.VerificationService"
        ) as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.verify_change.return_value = mock_verification
            MockService.return_value = mock_service_instance

            request = ChangeVerificationRequest(
                is_false_positive=True,
                feedback_reason="Test reason",
            )

            result = await verify_change(
                diff_id=diff_id,
                request=request,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.verify_change.assert_awaited_once_with(
                mock_db, diff_id, request, mock_user.id
            )
            assert result == mock_verification

    @pytest.mark.asyncio
    async def test_update_verification_endpoint(self, mock_db, mock_user):
        """Test PATCH /verifications/{verification_id} endpoint."""
        from app.api.modules.v1.scraping.routes.source_routes import update_verification

        verification_id = uuid.uuid4()
        mock_verification = ChangeVerification(
            id=verification_id,
            change_diff_id=uuid.uuid4(),
            verified_by=mock_user.id,
            is_false_positive=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        with patch(
            "app.api.modules.v1.scraping.routes.source_routes.VerificationService"
        ) as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.update_verification.return_value = mock_verification
            MockService.return_value = mock_service_instance

            update = ChangeVerificationUpdate(is_false_positive=False)

            result = await update_verification(
                verification_id=verification_id,
                update=update,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.update_verification.assert_awaited_once()
            assert result == mock_verification


class TestSuppressionRuleEndpoints:
    """Tests for suppression rule API endpoints."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        return User(id=uuid.uuid4(), email="test@example.com", is_active=True)

    @pytest.fixture
    def sample_source_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_suppression_rule_endpoint(
        self, mock_db, mock_user, sample_source_id
    ):
        """Test POST /{source_id}/suppression-rules endpoint."""
        from app.api.modules.v1.scraping.routes.source_routes import (
            create_suppression_rule,
        )

        mock_rule = SuppressionRule(
            id=uuid.uuid4(),
            source_id=sample_source_id,
            rule_type=SuppressionRuleType.FIELD_NAME,
            rule_pattern="timestamp",
            rule_description="Ignore timestamp changes",
            created_by=mock_user.id,
            is_active=True,
            created_at=datetime.now(),
        )

        with patch(
            "app.api.modules.v1.scraping.routes.source_routes.VerificationService"
        ) as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.create_suppression_rule.return_value = mock_rule
            MockService.return_value = mock_service_instance

            rule_data = SuppressionRuleCreate(
                rule_type=SuppressionRuleType.FIELD_NAME,
                rule_pattern="timestamp",
                rule_description="Ignore timestamp changes",
            )

            result = await create_suppression_rule(
                source_id=sample_source_id,
                rule_data=rule_data,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.create_suppression_rule.assert_awaited_once_with(
                mock_db, sample_source_id, rule_data, mock_user.id
            )
            assert result == mock_rule

    @pytest.mark.asyncio
    async def test_delete_suppression_rule_endpoint(self, mock_db, mock_user):
        """Test DELETE /suppression-rules/{rule_id} endpoint."""
        from app.api.modules.v1.scraping.routes.source_routes import (
            delete_suppression_rule,
        )

        rule_id = uuid.uuid4()

        with patch(
            "app.api.modules.v1.scraping.routes.source_routes.VerificationService"
        ) as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.delete_suppression_rule.return_value = True
            MockService.return_value = mock_service_instance

            result = await delete_suppression_rule(
                rule_id=rule_id,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.delete_suppression_rule.assert_awaited_once_with(
                mock_db, rule_id, mock_user.id
            )
            assert result is None


class TestMetricsEndpoint:
    """Tests for false positive metrics endpoint."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        return User(id=uuid.uuid4(), email="test@example.com", is_active=True)

    @pytest.fixture
    def sample_source_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_get_false_positive_metrics_endpoint(
        self, mock_db, mock_user, sample_source_id
    ):
        """Test GET /{source_id}/fp-metrics endpoint."""
        from app.api.modules.v1.scraping.routes.source_routes import (
            get_false_positive_metrics,
        )

        mock_metrics = FalsePositiveMetrics(
            source_id=sample_source_id,
            total_changes=100,
            verified_changes=50,
            false_positives=10,
            false_positive_rate=20.0,
            period_days=30,
        )

        with patch(
            "app.api.modules.v1.scraping.routes.source_routes.VerificationService"
        ) as MockService:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_false_positive_metrics.return_value = mock_metrics
            MockService.return_value = mock_service_instance

            result = await get_false_positive_metrics(
                source_id=sample_source_id,
                period_days=30,
                db=mock_db,
                current_user=mock_user,
            )

            mock_service_instance.get_false_positive_metrics.assert_awaited_once_with(
                mock_db, sample_source_id, 30
            )
            assert result == mock_metrics
            assert result.false_positive_rate == 20.0
