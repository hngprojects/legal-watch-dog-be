import asyncio
import pytest
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession


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
