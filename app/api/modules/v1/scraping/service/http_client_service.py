import logging
from typing import Dict, Any

import cloudscraper

from app.api.modules.v1.scraping.service.playwright_service import PlaywrightService

logger = logging.getLogger(__name__)


class HTTPClientService:
    """
    Service for fetching web content with CloudFlare bypass support.
    Handles HTTP requests with fallback to browser automation for protected sites.
    """

    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.browser = PlaywrightService()

    async def fetch_content(self, url: str, auth_creds: Dict[str, Any]) -> bytes:
        """
        Fetch URL content with CloudFlare bypass support.
        Handles both HTML and PDF responses with fallback to Playwright.

        Args:
            url: URL to fetch
            auth_creds: Authentication credentials if needed

        Returns:
            Raw content as bytes (HTML or PDF)

        Raises:
            Exception: If both fetch methods fail
        """
        try:
            response = self.scraper.get(url, timeout=30)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            logger.info(f"Fetched {url} - Content-Type: {content_type}")

            return response.content
        except Exception as e:
            logger.warning(f"cloudscraper failed: {e}. Falling back to Playwright.")
            # Fallback to Playwright for JavaScript-heavy sites
            return await self.browser.scrape(url, auth_creds)