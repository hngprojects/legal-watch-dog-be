import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.core.config import settings

TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True, scope="function")
def mock_redis():
    """
    Mock Redis client for all tests to avoid connection errors.
    This fixture is autouse=True so it applies to all tests automatically.
    """
    # Create a simple in-memory store to simulate Redis behavior
    redis_store = {}

    # Create a mock Redis client with async methods
    mock_redis_client = AsyncMock()

    async def mock_get(key):
        return redis_store.get(key)

    async def mock_set(key, value, **kwargs):
        redis_store[key] = str(value)
        return True

    async def mock_setex(key, seconds, value):
        redis_store[key] = str(value)
        return True

    async def mock_delete(*keys):
        count = 0
        for key in keys:
            if key in redis_store:
                del redis_store[key]
                count += 1
        return count

    async def mock_incr(key):
        current = int(redis_store.get(key, 0))
        new_value = current + 1
        redis_store[key] = str(new_value)
        return new_value

    async def mock_expire(key, seconds):
        return True

    async def mock_ttl(key):
        if key in redis_store:
            # For lockout keys, return 15 minutes in seconds
            if "lockout" in key:
                return 15 * 60  # 900 seconds = 15 minutes
            return 300
        return -1

    async def mock_exists(key):
        return 1 if key in redis_store else 0

    # Configure the mock methods
    mock_redis_client.get.side_effect = mock_get
    mock_redis_client.set.side_effect = mock_set
    mock_redis_client.setex.side_effect = mock_setex
    mock_redis_client.delete.side_effect = mock_delete
    mock_redis_client.incr.side_effect = mock_incr
    mock_redis_client.expire.side_effect = mock_expire
    mock_redis_client.ttl.side_effect = mock_ttl
    mock_redis_client.exists.side_effect = mock_exists
    mock_redis_client.close.return_value = None

    # Patch redis.from_url to return our mock instead of trying to connect
    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        # Reset the global _redis_client before each test
        import app.api.core.dependencies.redis_service as redis_module

        redis_module._redis_client = None
        yield mock_redis_client
        redis_module._redis_client = None


@pytest.fixture
def pg_sync_session():
    """
    Provide a synchronous PostgreSQL session for tests that need Postgres features
    (e.g., JSONB). Will create/drop all tables for the test run.
    """
    # Ensure a Postgres URL is configured
    if not settings.DATABASE_URL:
        pytest.skip("Postgres DB not configured for tests")

    # Convert async URL to sync URL for sync engine
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, echo=False)

    # Drop any existing tables first to ensure schema is recreated with the
    # current SQLModel definitions (this is important when tests run against
    # a database that may already have old schema from Alembic migrations).
    # Use raw SQL to drop tables with CASCADE to handle foreign key constraints
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("DROP SCHEMA public CASCADE;"))
        conn.execute(sqlalchemy.text("CREATE SCHEMA public;"))
        conn.commit()

    SQLModel.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up with CASCADE
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("DROP SCHEMA public CASCADE;"))
            conn.execute(sqlalchemy.text("CREATE SCHEMA public;"))
            conn.commit()


@pytest_asyncio.fixture
async def pg_async_session(event_loop):
    """
    Provide an async PostgreSQL session using `asyncpg`. This fixture creates and
    tears down tables for tests that require an async session.
    """
    if not settings.DATABASE_URL:
        pytest.skip("Postgres DB not configured for tests")

    # convert sync URL to asyncpg format
    async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False)
    async_session_maker_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        # ensure we start with a clean schema for the async Postgres fixture
        # Use CASCADE to handle foreign key constraints
        await conn.execute(sqlalchemy.text("DROP SCHEMA public CASCADE;"))
        await conn.execute(sqlalchemy.text("CREATE SCHEMA public;"))
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker_local() as session:
        yield session

    async with engine.begin() as conn:
        # Clean up with CASCADE
        await conn.execute(sqlalchemy.text("DROP SCHEMA public CASCADE;"))
        await conn.execute(sqlalchemy.text("CREATE SCHEMA public;"))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_session():
    """Create tables"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
