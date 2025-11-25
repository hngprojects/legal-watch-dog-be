import asyncio
from playwright.async_api import async_playwright
from typing import Dict, Any
import io


class PlaywrightService:
	"""Simple wrapper around Playwright to perform browser scraping.

	Keeps the browser-scraping logic out of higher-level services so it can be
	mocked, tested, or re-used from other services.
	"""

	async def scrape(self, url: str, creds: Dict[str, Any]) -> bytes:
		async with async_playwright() as p:
			browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
			context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
			page = await context.new_page()
			
			# Handle PDF downloads
			download_data = None
			download_event = asyncio.Event()
			
			async def handle_download(download):
				nonlocal download_data
				try:
					# Wait for download to complete and get the path
					path = await download.path()
					with open(path, 'rb') as f:
						download_data = f.read()
					download_event.set()
				except Exception as e:
					print(f"Download handling error: {e}")
			
			page.on("download", handle_download)
			
			try:
				# First try to navigate normally
				try:
					await page.goto(url, timeout=30000, wait_until="domcontentloaded")
					
					# Check if download started immediately
					if download_event.is_set():
						# Wait for download to complete
						await download_event.wait()
						return download_data
					
					# Wait a bit more for any delayed downloads
					await asyncio.sleep(3)
					
					if download_event.is_set():
						await download_event.wait()
						return download_data
					
					# No download, return page content
					try:
						await page.wait_for_load_state("networkidle", timeout=10000)
					except Exception:
						pass
					return (await page.content()).encode("utf-8")
					
				except Exception as e:
					# If navigation fails due to download, wait for download
					if "Download is starting" in str(e) or download_event.is_set():
						try:
							await asyncio.wait_for(download_event.wait(), timeout=30.0)
							return download_data
						except asyncio.TimeoutError:
							raise Exception("Download timed out")
					else:
						# Re-raise other navigation errors
						raise e
						
			finally:
				await browser.close()
