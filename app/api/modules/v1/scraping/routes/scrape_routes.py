from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.scraping.schemas.scrape_result_schema import (
    ScrapeResultCreate,
    ScrapeResultOut,
)
from app.api.modules.v1.scraping.models.scrape_result import ScrapeResult
from app.api.modules.v1.scraping.service.scraper import scrape_url


router = APIRouter()


@router.post("/", response_model=ScrapeResultOut)
async def scrape_endpoint(
    payload: ScrapeResultCreate, db: AsyncSession = Depends(get_db)
):
    data = await scrape_url(payload.url)

    obj = ScrapeResult(url=data["url"], title=data["title"], content=data["content"])
    db.add(obj)
    await db.commit()
    await db.refresh(obj)

    return obj
