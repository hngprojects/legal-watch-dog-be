# tests/modules/v1/tickets/service/test_ticket_creation_service.py
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_auto_ticket_with_admin_user():
    """Test creating an auto ticket when an admin user exists."""
    # Patch all imports before importing the service
    select_patch = "app.api.modules.v1.tickets.service.ticket_creation_service.select"
    user_patch = "app.api.modules.v1.tickets.service.ticket_creation_service.User"
    datetime_patch = "app.api.modules.v1.tickets.service.ticket_creation_service.datetime"

    with (
        patch(select_patch) as mock_select,
        patch(user_patch) as mock_user_class,
        patch(datetime_patch) as mock_datetime,
    ):
        # Import after patching
        from app.api.modules.v1.tickets.models.ticket_model import TicketPriority
        from app.api.modules.v1.tickets.service.ticket_creation_service import TicketService

        # Setup mocks
        mock_db = AsyncMock()

        # Mock datetime
        fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time

        # Mock User class attributes
        mock_user_class.organization_id = MagicMock()
        mock_user_class.organization_id.__eq__ = MagicMock(return_value=True)

        mock_user_class.is_active = MagicMock()
        mock_user_class.is_active.is_ = MagicMock(return_value=True)

        mock_user_class.is_superuser = MagicMock()
        mock_user_class.is_superuser.is_ = MagicMock(return_value=True)

        # Mock select chain
        mock_select_obj = MagicMock()
        mock_select.return_value = mock_select_obj
        mock_where_obj = MagicMock()
        mock_select_obj.where.return_value = mock_where_obj
        mock_limit_obj = MagicMock()
        mock_where_obj.limit.return_value = mock_limit_obj

        # Mock query execution result - CRITICAL FIX HERE
        mock_admin_user = MagicMock()
        mock_admin_user.id = uuid.uuid4()

        # Create a proper mock for scalars().first()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_admin_user

        # Create mock for execute() result - NOT an AsyncMock
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars

        # Make execute() return the mock result (not an AsyncMock)
        mock_db.execute.return_value = mock_execute_result

        # Mock test data
        mock_revision = MagicMock()
        mock_revision.id = uuid.uuid4()
        mock_revision.source_id = "test-source-123"

        mock_change_result = MagicMock()
        mock_change_result.change_summary = (
            "Multiple fields updated including address and contact information"
        )
        mock_change_result.risk_level = "HIGH"

        # Create service and execute
        service = TicketService(mock_db)
        result = await service.create_auto_ticket(
            revision=mock_revision,
            change_result=mock_change_result,
            project_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
        )

        # Assertions
        expected_title = f"Change Detected in Source {mock_revision.source_id}"
        assert result.title == expected_title

        rev_desc = f"Automatic ticket created from data revision {mock_revision.id}"
        assert rev_desc in result.description
        assert mock_change_result.change_summary in result.description
        assert f"Risk Level: {mock_change_result.risk_level}" in result.description
        assert result.status == "open"
        assert result.priority == TicketPriority.MEDIUM
        assert result.is_manual is False
        assert result.data_revision_id == mock_revision.id
        assert result.created_by_user_id == mock_admin_user.id
        assert result.assigned_to_user_id is None
        assert result.created_at == fixed_time
        assert result.updated_at == fixed_time


@pytest.mark.asyncio
async def test_create_auto_ticket_without_admin_user():
    """Test creating an auto ticket when no admin user exists."""
    select_patch = "app.api.modules.v1.tickets.service.ticket_creation_service.select"
    user_patch = "app.api.modules.v1.tickets.service.ticket_creation_service.User"

    with patch(select_patch) as mock_select, patch(user_patch) as mock_user_class:
        from app.api.modules.v1.tickets.service.ticket_creation_service import TicketService

        # Setup mocks
        mock_db = AsyncMock()

        # Mock User class attributes
        mock_user_class.organization_id = MagicMock()
        mock_user_class.organization_id.__eq__ = MagicMock(return_value=True)
        mock_user_class.is_active = MagicMock()
        mock_user_class.is_active.is_ = MagicMock(return_value=True)
        mock_user_class.is_superuser = MagicMock()
        mock_user_class.is_superuser.is_ = MagicMock(return_value=True)

        # Mock select chain
        mock_select_obj = MagicMock()
        mock_select.return_value = mock_select_obj
        mock_where_obj = MagicMock()
        mock_select_obj.where.return_value = mock_where_obj
        mock_limit_obj = MagicMock()
        mock_where_obj.limit.return_value = mock_limit_obj

        # Mock query to return None (no admin user) - CRITICAL FIX HERE
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Mock test data
        mock_revision = MagicMock()
        mock_revision.id = uuid.uuid4()
        mock_revision.source_id = "another-source"

        mock_change_result = MagicMock()
        mock_change_result.change_summary = "Minor configuration changes"
        mock_change_result.risk_level = "LOW"

        # Create service and execute
        service = TicketService(mock_db)
        result = await service.create_auto_ticket(
            revision=mock_revision,
            change_result=mock_change_result,
            project_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
        )

        # Assertions
        assert result.created_by_user_id is None
        expected_title = f"Change Detected in Source {mock_revision.source_id}"
        assert result.title == expected_title
        assert "Automatic ticket created from data revision" in result.description
        assert mock_change_result.change_summary in result.description
        assert f"Risk Level: {mock_change_result.risk_level}" in result.description
