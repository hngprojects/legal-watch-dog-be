import asyncio
import pytest
import pytest_asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture
def pg_sync_session():
    """
    Provide a synchronous PostgreSQL session for tests that need Postgres features
    (e.g., JSONB). Will create/drop all tables for the test run.
    """
    # Ensure a Postgres URL is configured
    if not settings.DATABASE_URL:
        pytest.skip("Postgres DB not configured for tests")

    engine = create_engine(settings.DATABASE_URL, echo=False)

    # Drop any existing tables first to ensure schema is recreated with the
    # current SQLModel definitions (this is important when tests run against
    # a database that may already have old schema from Alembic migrations).
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        SQLModel.metadata.drop_all(engine)


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
    async_session_maker_local = _async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        # ensure we start with a clean schema for the async Postgres fixture
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker_local() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


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
