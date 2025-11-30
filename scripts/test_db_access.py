"""Test database access from Celery context."""

import asyncio

from sqlalchemy import select

from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.tasks import get_celery_session


async def test_db():
    """Test database connectivity."""
    print("=" * 60)
    print("TESTING DATABASE ACCESS")
    print("=" * 60)
    
    async with get_celery_session() as db:
        # Count sources
        query = select(Source).where(Source.is_deleted.is_(False))
        result = await db.execute(query)
        sources = result.scalars().all()
        
        print("\n✅ Database connected!")
        print(f"Found {len(sources)} active sources")
        
        for source in sources[:5]:  # Show first 5
            print(f"  - {source.name} ({source.source_type})")

if __name__ == "__main__":
    asyncio.run(test_db())

