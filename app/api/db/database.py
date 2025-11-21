from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.api.core.config import settings

BASE_DIR = Path(__file__).resolve().parent

DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_USER = settings.DB_USER
DB_PASS = settings.DB_PASS
DB_NAME = settings.DB_NAME
DB_TYPE = settings.DB_TYPE


def get_db_url(test_mode: bool = False) -> str:
    """
    Constructs and returns the database URL for async SQLModel engines.
    """
    if DB_TYPE == "sqlite" or test_mode:
        db_file = "test.db" if test_mode else "db.sqlite3"
        return f"sqlite+aiosqlite:///{BASE_DIR}/{db_file}"

    return f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


DATABASE_URL = get_db_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = SQLModel


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
