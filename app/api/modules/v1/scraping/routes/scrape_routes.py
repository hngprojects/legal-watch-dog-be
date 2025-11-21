from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.scraping.service.scraper_service import scrape_url_and_store

router = APIRouter(prefix="/scraper", tags=["Scraper"])

@router.post(
    "/scrape",
    summary="Scrape a URL and store the result",
    status_code=status.HTTP_200_OK,
    description="Web scraper",
)

async def scrape(url: str, session: AsyncSession = Depends(get_db)):
    return await scrape_url_and_store(url, session)
