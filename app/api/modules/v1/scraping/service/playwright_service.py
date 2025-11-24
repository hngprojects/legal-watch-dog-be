from playwright.async_api import async_playwright
from typing import Dict, Any


class PlaywrightService:
	"""Simple wrapper around Playwright to perform browser scraping.

	Keeps the browser-scraping logic out of higher-level services so it can be
	mocked, tested, or re-used from other services.
	"""

	async def scrape(self, url: str, creds: Dict[str, Any]) -> bytes:
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
			context = await browser.new_context(user_agent="Mozilla/5.0 (EnterpriseBot/1.0)")
			page = await context.new_page()
			try:
				await page.goto(url, timeout=60000, wait_until="domcontentloaded")
				try:
					await page.wait_for_load_state("networkidle", timeout=10000)
				except Exception:
					# It's okay if networkidle does not happen; we still want page.content()
					pass
				return (await page.content()).encode("utf-8")
			finally:
				await browser.close()
