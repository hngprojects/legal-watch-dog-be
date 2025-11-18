import asyncio
import pytest
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
import sqlalchemy

# Testing note: the project's Organization model uses PostgreSQL's JSONB type.
# When running tests against SQLite (the in-memory test DB) SQLAlchemy's
# SQLite compiler doesn't understand JSONB. To keep tests simple and isolated
# we alias JSONB to the generic JSON type at test time when the test DB is
# SQLite. This is a safe shim for tests only and does not change production
# models.
try:
    from sqlalchemy.dialects import postgresql as _pg
    if 'sqlite' in "sqlite+aiosqlite://":
        # alias JSONB to generic JSON so table creation succeeds under SQLite
        _pg.JSONB = sqlalchemy.JSON
except Exception:
    # if import fails or aliasing isn't possible, continue — tests may still fail
    pass


TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Provides a session-scoped asyncio event loop for tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_session(event_loop):
    """
    Synchronous fixture that runs async DB setup/teardown manually
    for pytest 9 strict mode compatibility.
    """
    async def _get_session():
        # ensure model modules are imported so relationships/back_populates are
        # registered before SQLModel attempts mapper configuration. This avoids
        # ordering issues when models reference each other across modules.
        try:
            import app.api.modules.v1.onboarding.models.team_invitation  # noqa: F401
            import app.api.modules.v1.organization.models.organization_model  # noqa: F401
            import app.api.modules.v1.users.models.users_model  # noqa: F401
            # explicitly configure mappers now that all model modules are imported
            try:
                from sqlalchemy.orm import configure_mappers
                configure_mappers()
            except Exception:
                pass
        except Exception:
            # if imports fail, continue and let create_all surface errors
            pass

        # create tables
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        # provide session to test
        async with async_session_maker() as session:
            yield session

        # drop tables
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    # return generator for async test
    return _get_session()
