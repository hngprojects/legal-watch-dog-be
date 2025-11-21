from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.scraping.models.web_scraper_model import WebScraper
from app.api.modules.v1.scraping.storage.minio_storage import (
    fetch_raw_content_from_minio,
    upload_raw_content,
)


async def scrape_url_and_store(url: str, session: AsyncSession):
    # --- SCRAPE WITH PLAYWRIGHT ---
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)

        title = await page.title()
        raw_html = (await page.content()).encode("utf-8")

        await browser.close()

    # --- UPLOAD TO MINIO ---
    minio_key = upload_raw_content(raw_html, extension="html")

    # --- CREATE ScrapeResult ---
    scrape_result = WebScraper(url=url, title=title)
    session.add(scrape_result)
    session.commit()
    session.refresh(scrape_result)

    # --- CREATE DataRevision ---
    # revision = DataRevision(
    #     scrape_result_id=scrape_result.id,
    #     minio_key=minio_key,
    #     revision_number=1
    # )
    # session.add(revision)
    # session.commit()

    # --- Fetch raw content back for API response ---
    content = fetch_raw_content_from_minio(minio_key)

    return {
        "id": scrape_result.id,
        "url": scrape_result.url,
        "title": scrape_result.title,
        "content": content.decode("utf-8")
    }
