from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.core.dependencies.auth import get_current_user
from app.api.modules.v1.tickets.models.ticket_model import TicketStatus
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import TicketResponse
from main import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_close_ticket_success(test_client):
    ticket_id = uuid4()
    project_id = uuid4()
    organization_id = uuid4()
    user_id = uuid4()

    mock_ticket = TicketResponse(
        id=ticket_id,
        title="Test Ticket",
        content="Something happened",
        priority="low",
        is_manual=False,
        data_revision_id=uuid4(),
        source_id=uuid4(),
        created_by_user_id=user_id,
        assigned_by_user_id=None,
        assigned_to_user_id=None,
        project_id=project_id,
        organization_id=organization_id,
        status=TicketStatus.CLOSED.value,
        description="Closing notes: Issue resolved",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        closed_at="2024-01-01T00:00:00Z",
    )

    mock_user = Mock(id=user_id)

    app.dependency_overrides[get_current_user] = lambda: mock_user

    try:
        with (
            patch("app.api.db.database.get_db") as mock_db,
            patch("app.api.core.dependencies.auth.TenantGuard.get_membership") as mock_membership,
            patch(
                "app.api.modules.v1.tickets.service.close_ticket_service.TicketService.close_ticket"
            ) as mock_close,
        ):
            db_session = AsyncMock()
            mock_db.return_value = db_session

            mock_membership.return_value = True

            mock_close.return_value = mock_ticket

            payload = {"closing_notes": "Issue resolved"}

            url = (
                f"/api/v1/organizations/{organization_id}/projects/{project_id}"
                f"/tickets/{ticket_id}/close"
            )

            response = test_client.patch(url, json=payload)

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "SUCCESS"
            assert data["message"] == "Ticket closed successfully"
            assert data["data"]["id"] == str(ticket_id)
            assert data["data"]["status"] == "closed"
            assert "Issue resolved" in data["data"]["description"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
