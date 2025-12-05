import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_create_auto_ticket_with_mocker(mocker):
    """Using pytest-mock for cleaner mocking."""

    mock_select = mocker.patch("app.api.modules.v1.tickets.service.ticket_creation_service.select")
    mock_user_class = mocker.patch(
        "app.api.modules.v1.tickets.service.ticket_creation_service.User"
    )
    mock_datetime = mocker.patch(
        "app.api.modules.v1.tickets.service.ticket_creation_service.datetime"
    )

    from app.api.modules.v1.tickets.service.ticket_creation_service import TicketService

    mock_db = mocker.AsyncMock()

    fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = fixed_time

    mock_user_class.organization_id = mocker.Mock()
    mock_user_class.organization_id.__eq__ = mocker.Mock(return_value=True)
    mock_user_class.is_active = mocker.Mock()
    mock_user_class.is_active.is_ = mocker.Mock(return_value=True)
    mock_user_class.is_superuser = mocker.Mock()
    mock_user_class.is_superuser.is_ = mocker.Mock(return_value=True)

    mock_select_obj = mocker.Mock()
    mock_select.return_value = mock_select_obj
    mock_where_obj = mocker.Mock()
    mock_select_obj.where.return_value = mock_where_obj
    mock_limit_obj = mocker.Mock()
    mock_where_obj.limit.return_value = mock_limit_obj

    mock_user_instance = mocker.Mock()
    mock_user_instance.id = uuid.uuid4()

    mock_scalar_result = mocker.Mock()
    mock_scalar_result.first.return_value = mock_user_instance

    mock_execute_result = mocker.Mock()
    mock_execute_result.scalars.return_value = mock_scalar_result
    mock_db.execute.return_value = mock_execute_result

    mock_revision = mocker.Mock()
    mock_revision.id = uuid.uuid4()
    mock_revision.source_id = "test-source-123"

    mock_change_result = mocker.Mock()
    mock_change_result.change_summary = "Important changes detected"
    mock_change_result.risk_level = "HIGH"

    service = TicketService(mock_db)
    result = await service.create_auto_ticket(
        revision=mock_revision,
        change_result=mock_change_result,
        project_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
    )

    assert result is not None
    assert result.title == "Change Detected in Source test-source-123"
    assert result.created_by_user_id == mock_user_instance.id
    assert "Important changes detected" in result.description
    assert "Risk Level: HIGH" in result.description

    mock_db.add.assert_called_once_with(result)
    mock_db.flush.assert_called_once()
    mock_db.refresh.assert_called_once_with(result)


@pytest.mark.asyncio
async def test_create_auto_ticket_basic_coverage(mocker):
    """Basic test for coverage."""

    mocker.patch("app.api.modules.v1.tickets.service.ticket_creation_service.select")
    mocker.patch("app.api.modules.v1.tickets.service.ticket_creation_service.User")
    mocker.patch("app.api.modules.v1.tickets.service.ticket_creation_service.datetime")

    from app.api.modules.v1.tickets.service.ticket_creation_service import TicketService

    mock_db = mocker.AsyncMock()
    service = TicketService(mock_db)

    assert service.db == mock_db
