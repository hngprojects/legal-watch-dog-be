import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.scraping.service.scraper_service import scrape_url_and_store
from app.api.utils.response_payloads import fail_response, success_response

router = APIRouter(prefix="/scraper", tags=["Scraper"])

logger = logging.getLogger(__name__)


@router.post(
    "/scrape",
    summary="Scrape a URL and store the result",
    description="Scrapes a webpage using Playwright, stores raw HTML in MinIO.",
)
async def scrape(url: str, session: AsyncSession = Depends(get_db)):
    try:
        logger.info(f"[SCRAPER] Starting scrape for URL: {url}")

        result = await scrape_url_and_store(url, session)

        logger.info(f"[SCRAPER] Successfully scraped and stored content for URL: {url}")

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Scraping completed successfully",
            data=result
        )

    except Exception as e:
        logger.error(f"[SCRAPER] Error scraping URL {url}: {e}", exc_info=True)

        return fail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to scrape the provided URL",
            error={"detail": str(e)}
        )
