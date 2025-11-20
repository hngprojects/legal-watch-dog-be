from playwright.async_api import async_playwright


async def scrape_url(url: str) -> dict:
    """Basic scraper that returns page title + innerText."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="domcontentloaded")

        title = await page.title()
        content = await page.inner_text("body")

        await browser.close()

    return {"url": url, "title": title, "content": content}
