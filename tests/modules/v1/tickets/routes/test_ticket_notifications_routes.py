from unittest.mock import patch

import pytest
from httpx import AsyncClient

from main import app


@pytest.mark.asyncio
async def test_trigger_ticket_notification_route():
    """
    Ensures route queues Celery task and returns correct response.
    """
    with patch(
        "app.api.modules.v1.notifications.routes.ticket_notification_routes.send_ticket_notifications"
    ) as mocked_task:
        mocked_task.delay.return_value = None

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/notifications/tickets/123/send?message=hello")

        assert response.status_code == 200
        assert response.json() == {"detail": "Notification task queued"}

        mocked_task.delay.assert_called_once_with("123", "hello")
