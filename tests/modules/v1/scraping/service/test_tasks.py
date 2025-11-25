import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.config import settings
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.tasks import (
    CELERY_DLQ_KEY,
    dispatch_due_sources,
    get_next_scrape_time,
    scrape_source,
)


@pytest.mark.parametrize(
    "frequency, expected_delta",
    [
        ("DAILY", timedelta(days=1)),
        ("WEEKLY", timedelta(weeks=1)),
        ("MONTHLY", timedelta(days=30)),
        ("HOURLY", timedelta(hours=1)),
        ("UNKNOWN", timedelta(days=1)),
    ],
)
def test_get_next_scrape_time(frequency, expected_delta):
    now = datetime.now(timezone.utc)
    next_time = get_next_scrape_time(now, frequency)
    assert abs((next_time - now) - expected_delta) < timedelta(seconds=1)


def test_scrape_source_success():
    """Tests the successful scraping of a source."""
    source_id = str(uuid.uuid4())
    source = Source(
        id=uuid.UUID(source_id),
        jurisdiction_id=uuid.uuid4(),
        name="Test Source",
        url="http://example.com",
        scrape_frequency="HOURLY",
        next_scrape_time=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    # Mock the AsyncSession as a MagicMock to control async vs sync methods
    mock_db = MagicMock()
    # Configure async methods
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.close = AsyncMock()
    # Configure sync methods
    mock_db.add = MagicMock()

    # Configure execute to return a mock that has a .scalars().first() method chain
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = source
    mock_db.execute.return_value = mock_result

    with (
        patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        mock_context = MagicMock()
        mock_context.retries = 0
        scrape_source.push_request(mock_context)

        try:
            result = scrape_source.run(source_id)
        finally:
            scrape_source.pop_request()

    assert "scraped successfully" in result
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()
    mock_db.add.assert_called_once_with(source)

    # Verify stats updated
    assert source.last_scraped_at is not None
    assert source.last_error is None


def test_scrape_source_not_found():
    """Tests the case where the source ID does not exist."""
    non_existent_id = str(uuid.uuid4())

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.close = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    with patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        result = scrape_source.run(non_existent_id)

    assert "not found" in result


def test_scrape_source_dlq_on_max_retries():
    """Tests that a failed scrape_source task is moved to DLQ after max retries."""
    source_id = str(uuid.uuid4())

    # Mock Redis
    with (
        patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal"),
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
        patch(
            "app.api.modules.v1.scraping.service.tasks._scrape_source_async", new_callable=MagicMock
        ) as mock_scrape_async,
    ):
        # Simulate failure in scraping logic directly
        mock_scrape_async.side_effect = Exception("Simulated scraping failure")

        mock_redis_client = MagicMock()
        mock_redis_cls.return_value = mock_redis_client

        max_retries = settings.SCRAPE_MAX_RETRIES

        for i in range(max_retries):
            scrape_source.push_request(id="test_task_id", args=[source_id], retries=i)
            with pytest.raises(Exception):
                scrape_source.run(source_id)
            scrape_source.pop_request()

        scrape_source.push_request(id="test_task_id", args=[source_id], retries=max_retries)

        result = scrape_source.run(source_id)
        scrape_source.pop_request()

        assert "moved to DLQ" in result
        mock_redis_client.lpush.assert_called_once()

        called_args, _ = mock_redis_client.lpush.call_args
        assert called_args[0] == CELERY_DLQ_KEY
        dlq_entry = json.loads(called_args[1])
        assert dlq_entry["task_id"] == "test_task_id"

        # Verify circuit breaker was called
        # Note: Since it's called via asyncio.run inside the exception handler,
        # we need to ensure our mock was set up to capture this.
        # However, we mocked _scrape_source_async, not _handle_scrape_failure_async.
        # We need to mock _handle_scrape_failure_async in the test setup.

    # Re-run the test with _handle_scrape_failure_async mocked
    with (
        patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal"),
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
        patch(
            "app.api.modules.v1.scraping.service.tasks._scrape_source_async", new_callable=MagicMock
        ) as mock_scrape_async,
        patch(
            "app.api.modules.v1.scraping.service.tasks._handle_scrape_failure_async",
            new_callable=MagicMock,
        ) as mock_handle_failure,
    ):
        mock_scrape_async.side_effect = Exception("Simulated scraping failure")
        mock_redis_client = MagicMock()
        mock_redis_cls.return_value = mock_redis_client

        scrape_source.push_request(
            id="test_task_id", args=[source_id], retries=settings.SCRAPE_MAX_RETRIES
        )
        result = scrape_source.run(source_id)
        scrape_source.pop_request()

        assert "moved to DLQ" in result
        # Verify circuit breaker called
        mock_handle_failure.assert_called_once()


def test_dispatch_due_sources_acquires_lock_and_dispatches():
    """Tests that the dispatcher acquires a lock and dispatches tasks."""
    source1 = Source(id=uuid.uuid4(), name="Due Source 1", scrape_frequency="HOURLY")
    source2 = Source(id=uuid.uuid4(), name="Due Source 2", scrape_frequency="HOURLY")

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.close = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    # Configure mock results for batching
    mock_result_batch1 = MagicMock()
    mock_result_batch1.scalars.return_value.all.return_value = [source1, source2]

    mock_result_batch2 = MagicMock()
    mock_result_batch2.scalars.return_value.all.return_value = []

    # side_effect on the AWAITED result of execute
    # We need to ensure that the return values are treated as the result of the await
    mock_db.execute.side_effect = [mock_result_batch1, mock_result_batch2]

    with (
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
        patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls,
        patch.object(dispatch_due_sources, "app") as mock_app,
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_cls.return_value = mock_redis_instance

        mock_session_cls.return_value.__aenter__.return_value = mock_db

        mock_app.send_task = MagicMock()

        result = dispatch_due_sources.run()

    assert "Dispatched 2 sources" in result
    assert mock_redis_instance.set.call_count == 1
    assert mock_app.send_task.call_count == 2

    # Verify DB interactions
    assert mock_db.execute.call_count == 2
    assert mock_db.add.call_count == 2
    assert mock_db.commit.call_count == 2


def test_dispatch_due_sources_lock_already_held():
    """Tests that the dispatcher skips if the lock is already held."""
    with patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls:
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = False

        mock_redis_cls.return_value = mock_redis_instance

        result = dispatch_due_sources.run()

    assert "Skipped" in result
    assert mock_redis_instance.set.call_count == 1


def test_dispatch_due_sources_no_due_sources():
    """Tests that the dispatcher does nothing if no sources are due."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.close = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    with (
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
        patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls,
        patch.object(dispatch_due_sources, "app") as mock_app,
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_cls.return_value = mock_redis_instance

        mock_session_cls.return_value.__aenter__.return_value = mock_db

        mock_app.send_task = MagicMock()

        result = dispatch_due_sources.run()

    assert result == "No sources to dispatch."
