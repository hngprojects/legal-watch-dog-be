from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(scope="session", autouse=True)
def setup_patches():
    """
    Session-wide patches for cryptography and app config.
    `autouse=True` ensures this runs before any tests.
    """
    # Mock Fernet BEFORE any app imports to prevent key validation errors
    mock_fernet = MagicMock()
    mock_fernet.encrypt.return_value.decode.return_value = "mock_encrypted_value"
    mock_fernet.decrypt.return_value.decode.return_value = (
        '{"username": "test", "password": "secret"}'
    )

    # It's better to manage patches with start/stop or as context managers
    p1 = patch("cryptography.fernet.Fernet", return_value=mock_fernet)
    p2 = patch("app.api.core.config.get_cipher_suite", return_value=mock_fernet)

    p1.start()
    p2.start()

    yield

    p1.stop()
    p2.stop()


# Now import the app modules, after patches are set up
from app.api.core.config import settings  # noqa: E402

# Import all models to ensure they are registered with SQLAlchemy before creating tables

TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def mock_encryption(monkeypatch):
    """Set a valid encryption key for testing"""
    valid_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", valid_key)


# placeholder
@pytest.fixture
def mock_encrypt_auth_details():
    """Mock the encrypt_auth_details utility function."""
    with patch("app.api.modules.v1.scraping.service.source_service.encrypt_auth_details") as mock:
        mock.return_value = "mock_encrypted_value"
        yield mock


@pytest.fixture(autouse=True, scope="function")
def mock_redis(monkeypatch):
    """
    Mock Redis client for all tests to avoid connection errors.
    This fixture is autouse=True so it applies to all tests automatically.
    """
    # Set a mock Redis URL
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")

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

    # Patch ConnectionPool.from_url to return a mock pool
    mock_pool = MagicMock()
    mock_pool.disconnect = AsyncMock()

    # Patch both the ConnectionPool and Redis client creation
    with (
        patch("redis.asyncio.connection.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis", return_value=mock_redis_client),
    ):
        # Reset the global _redis_client before each test
        import app.api.core.dependencies.redis_service as redis_module

        redis_module._redis_client = None
        redis_module._connection_pool = None
        yield mock_redis_client
        redis_module._redis_client = None
        redis_module._connection_pool = None


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

    # Create all tables
    SQLModel.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up with CASCADE to handle foreign key dependencies
        with engine.begin() as conn:
            # Drop tables in correct order or use CASCADE
            for table in reversed(SQLModel.metadata.sorted_tables):
                conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
        engine.dispose()


@pytest_asyncio.fixture
async def pg_async_session():
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
        # Drop all tables individually instead of dropping the entire schema
        # This avoids permission issues with DROP SCHEMA
        try:
            # Get all table names
            result = await conn.execute(
                text("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
            )
            tables = [row[0] for row in result.fetchall()]
            
            # Drop each table with CASCADE
            for table in tables:
                await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
            
            # Drop all types (enums)
            result = await conn.execute(
                text("""
                    SELECT typname FROM pg_type 
                    WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                    AND typtype = 'e'
                """)
            )
            types = [row[0] for row in result.fetchall()]
            for type_name in types:
                await conn.execute(text(f'DROP TYPE IF EXISTS "{type_name}" CASCADE'))
                
        except Exception:
            # If we can't drop tables, just continue - might be first run
            pass
            
        # Create all tables fresh
        await conn.run_sync(SQLModel.metadata.create_all)
        # Add missing columns that exist in model but not auto-created
        await conn.execute(
            text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='projects' AND column_name='is_deleted'
                ) THEN
                    ALTER TABLE projects
                    ADD COLUMN is_deleted BOOLEAN DEFAULT false NOT NULL,
                    ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
                END IF;
            END $$;
        """)
        )

    async with async_session_maker_local() as session:
        yield session
        await session.rollback()

    # Clean up data - using TRUNCATE instead of DELETE (faster)
    async with async_session_maker_local() as session:
        result = await session.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                AND table_name NOT LIKE 'alembic%'
            """)
        )
        tables = [row[0] for row in result.fetchall()]

        if tables:
            # TRUNCATE is faster than DELETE and resets sequences
            tables_str = ", ".join(f'"{t}"' for t in tables)
            try:
                await session.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE"))
                await session.commit()
            except Exception:
                # Fallback to original approach if TRUNCATE fails
                for table in reversed(SQLModel.metadata.sorted_tables):
                    await session.execute(table.delete())
                await session.commit()

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session():
    """Create tables for SQLite test session, excluding PostgreSQL-specific tables"""

    # Create only tables that don't have PostgreSQL-specific features
    def create_sqlite_tables(connection, **kw):
        """Create tables but skip those with TSVECTOR columns (PostgreSQL-specific)"""

        # Create a copy of metadata for SQLite
        sqlite_metadata = SQLModel.metadata.__class__()

        for table in SQLModel.metadata.sorted_tables:
            # Skip tables with TSVECTOR columns (like data_revisions)
            has_tsvector = any(
                hasattr(col.type, "__class__") and col.type.__class__.__name__ == "TSVECTOR"
                for col in table.columns
            )
            if not has_tsvector:
                table.to_metadata(sqlite_metadata)

        sqlite_metadata.create_all(connection)

    async with engine.begin() as conn:
        await conn.run_sync(create_sqlite_tables)

    async with async_session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
