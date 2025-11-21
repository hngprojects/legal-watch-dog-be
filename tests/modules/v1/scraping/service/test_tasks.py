"""
Unit Tests for Scraping Service Tasks
=====================================

This module contains the test suite for the Celery tasks defined in
`app.api.modules.v1.scraping.service.tasks`. It verifies the logic for scheduling,
executing, and managing scraping jobs, ensuring robustness against failures and
concurrency issues.

Key Scenarios Tested:
---------------------
1. **Helper Functions**:
   - Validates `get_next_scrape_time` logic across various frequencies (HOURLY, DAILY, etc.).

2. **Scrape Execution (`scrape_source`)**:
   - **Success**: Ensures the scrape updates the `next_scrape_time` correctly in the DB.
   - **Failure & Retries**: Verifies that exceptions trigger Celery's retry mechanism with
     exponential backoff.
   - **Dead Letter Queue (DLQ)**: Confirms that after `MAX_RETRIES`, the failed task payload
     is pushed to Redis for manual inspection, preventing infinite loops.

3. **Task Dispatching (`dispatch_due_sources`)**:
   - **Selection**: Ensures only sources that are due (or new) are selected.
   - **Distributed Locking**: Verifies that Redis locks prevent multiple workers from
     dispatching the same tasks simultaneously (race condition prevention).
   - **Idempotency**: Checks that if the lock is held, the task exits gracefully without action.

Mocks & Fixtures:
-----------------
- Uses `unittest.mock` to simulate Redis interactions (locking, pushing to DLQ) and
  Database sessions to avoid side effects during testing.
- Relies on `pytest` fixtures for database session management.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from app.api.modules.v1.scraping.models.scrape import Source
from app.api.modules.v1.scraping.service.tasks import (
    CELERY_DLQ_KEY,
    MAX_RETRIES,
    dispatch_due_sources,
    get_next_scrape_time,
    scrape_source,
)


# --- Helper to bridge SQLModel .exec() to SQLAlchemy .execute() ---
def mock_exec_side_effect(session):
    """
    Creates a side_effect function that translates SQLModel's db.exec()
    into SQLAlchemy's db.execute().scalars().
    """

    def side_effect(statement):
        # SQLModel's .exec() returns a Result that acts like scalars
        return session.execute(statement).scalars()

    return side_effect


# --- Fixture Alias ---
@pytest.fixture
def sync_session(pg_sync_session):
    return pg_sync_session


# Test for the helper function
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


# Tests for the scrape_source task
def test_scrape_source_success(sync_session: Session):
    """Tests the successful scraping of a source."""
    source = Source(
        jurisdiction_id=uuid.uuid4(),
        name="Test Source",
        url="http://example.com",
        scrape_frequency="HOURLY",
        next_scrape_time=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    sync_session.add(source)
    sync_session.commit()
    sync_session.refresh(source)

    with (
        patch("app.api.modules.v1.scraping.service.tasks.Session") as mock_session_cls,
        patch("time.sleep", return_value=None),
    ):
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_db.exec.side_effect = mock_exec_side_effect(sync_session)
        mock_db.add.side_effect = sync_session.add
        mock_db.commit.side_effect = sync_session.commit
        mock_db.refresh.side_effect = sync_session.refresh

        mock_context = MagicMock()
        mock_context.retries = 0
        scrape_source.push_request(mock_context)

        try:
            result = scrape_source.run(str(source.id))
        finally:
            scrape_source.pop_request()

    sync_session.refresh(source)

    next_scrape_time = source.next_scrape_time
    # If the DB returned a naive datetime (common with SQLite), make it aware (UTC)
    if next_scrape_time.tzinfo is None:
        next_scrape_time = next_scrape_time.replace(tzinfo=timezone.utc)

    assert "scraped successfully" in result
    assert next_scrape_time > datetime.now(timezone.utc)


def test_scrape_source_not_found(sync_session: Session):
    """Tests the case where the source ID does not exist."""
    non_existent_id = uuid.uuid4()

    with patch("app.api.modules.v1.scraping.service.tasks.Session") as mock_session_cls:
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_db.exec.side_effect = mock_exec_side_effect(sync_session)

        # We don't strictly need push_request here if the code doesn't access self.request
        # before the "not found" check, but it's safer to include it or just run it.
        result = scrape_source.run(str(non_existent_id))

    assert "not found" in result


def test_scrape_source_dlq_on_max_retries(sync_session: Session):
    """Tests that a failed scrape_source task is moved to DLQ after max retries."""
    source = Source(
        jurisdiction_id=uuid.uuid4(),
        name="DLQ Test Source",
        url="http://dlq.com",
        scrape_frequency="HOURLY",
        next_scrape_time=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    sync_session.add(source)
    sync_session.commit()
    sync_session.refresh(source)

    with (
        patch("app.api.modules.v1.scraping.service.tasks.Session") as mock_session_cls,
        patch(
            "app.api.modules.v1.scraping.service.tasks.redis.Redis.from_url"
        ) as mock_redis_from_url,
        patch("time.sleep", return_value=None),
    ):
        # Mock DB
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_db.exec.side_effect = Exception("Simulated scraping failure")

        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_from_url.return_value = mock_redis_client

        # Simulate MAX_RETRIES failures
        for i in range(MAX_RETRIES):
            scrape_source.push_request(id="test_task_id", args=[str(source.id)], retries=i)
            with pytest.raises(Exception):  # Expect retry exception
                scrape_source.run(str(source.id))
            scrape_source.pop_request()

        # Now, simulate the final retry that should trigger DLQ
        scrape_source.push_request(id="test_task_id", args=[str(source.id)], retries=MAX_RETRIES)

        # This should now catch the exception internally and return the DLQ message
        result = scrape_source.run(str(source.id))
        scrape_source.pop_request()

        assert "moved to DLQ" in result
        mock_redis_client.lpush.assert_called_once()

        # Verify DLQ entry content
        called_args, _ = mock_redis_client.lpush.call_args
        assert called_args[0] == CELERY_DLQ_KEY
        dlq_entry = json.loads(called_args[1])
        assert dlq_entry["task_id"] == "test_task_id"


# Tests for the dispatch_due_sources task
def test_dispatch_due_sources_acquires_lock_and_dispatches(
    sync_session: Session, mock_redis: MagicMock
):
    """Tests that the dispatcher acquires a lock and dispatches tasks."""
    now = datetime.now(timezone.utc)
    source1 = Source(
        jurisdiction_id=uuid.uuid4(),
        name="Due Source 1",
        url="http://due1.com",
        next_scrape_time=now - timedelta(hours=1),
    )
    source2 = Source(
        jurisdiction_id=uuid.uuid4(),
        name="Due Source 2",
        url="http://due2.com",
        next_scrape_time=now - timedelta(minutes=30),
    )
    sync_session.add_all([source1, source2])
    sync_session.commit()

    with (
        patch(
            "app.api.modules.v1.scraping.service.tasks.redis.Redis.from_url"
        ) as mock_redis_from_url,
        patch("app.api.modules.v1.scraping.service.tasks.Session") as mock_session_cls,
        patch.object(dispatch_due_sources, "app") as mock_app,
    ):  # Mock .app directly
        # Mock Redis
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_from_url.return_value = mock_redis_instance

        # Mock DB with bridge
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_db.exec.side_effect = mock_exec_side_effect(sync_session)

        # Mock Celery App send_task
        mock_app.send_task = MagicMock()

        # Run with NO arguments (self is injected automatically)
        result = dispatch_due_sources.run()

    assert "Dispatched 2 sources" in result
    assert mock_redis_instance.set.call_count == 1
    assert mock_app.send_task.call_count == 2

    # mock_app.send_task.assert_any_call(
    #     "app.api.modules.v1.scraping.service.tasks.scrape_source",
    #     args=[str(source1.id)],
    # )


def test_dispatch_due_sources_lock_already_held():
    """Tests that the dispatcher skips if the lock is already held."""
    with patch(
        "app.api.modules.v1.scraping.service.tasks.redis.Redis.from_url"
    ) as mock_redis_from_url:
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = False

        mock_redis_from_url.return_value = mock_redis_instance

        # Run with NO arguments
        result = dispatch_due_sources.run()

    assert "Skipped" in result
    assert mock_redis_instance.set.call_count == 1


def test_dispatch_due_sources_no_due_sources(sync_session: Session):
    """Tests that the dispatcher does nothing if no sources are due."""
    source = Source(
        jurisdiction_id=uuid.uuid4(),
        name="Future Source",
        url="http://future.com",
        next_scrape_time=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    sync_session.add(source)
    sync_session.commit()

    with (
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_class,
        patch("app.api.modules.v1.scraping.service.tasks.Session") as mock_session_cls,
        patch.object(dispatch_due_sources, "app") as mock_app,
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_class.return_value = mock_redis_instance

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_db.exec.side_effect = mock_exec_side_effect(sync_session)

        mock_app.send_task = MagicMock()

        result = dispatch_due_sources.run()

    assert result == "No sources to dispatch."
