import logging
from bs4 import BeautifulSoup
from readability import Document
from fastapi.concurrency import run_in_threadpool
from app.api.modules.v1.scraping.service.minio_client import read_object, write_object
import re


logger = logging.getLogger(__name__)
EXTRACTOR_VERSION = "1.1.0"


def clean_text(text: str) -> str:
    """
    Clean extracted text by removing extra whitespace and special characters.
    """
    if not text:
        return ""
    # collapse multiple spaces/newlines/tabs into a single space
    text = re.sub(r"\s+", " ", text)
    # replace non-breaking spaces with normal spaces
    text = text.replace("\xa0", " ")
    # trim leading/trailing spaces
    return text.strip()


class TextExtractorService:
    """
    Async text extraction from HTML stored in MinIO.
    Steps:
        1. Read raw HTML
        2. Remove noise tags/elements
        3. Extract text (Soup + Readability fallback)
        4. Clean text
        5. Save to MinIO (optional)
    """

    # ---------------------- ASYNC PUBLIC METHODS -------------------------

    async def extract_from_html(self, bucket: str, object_name: str) -> str:
        logger.info(f"[Extractor v{EXTRACTOR_VERSION}] Reading HTML: {bucket}/{object_name}")

        # Read HTML from MinIO (async wrapper)
        try:
            raw_html = await run_in_threadpool(read_object, bucket, object_name)
        except Exception as e:
            logger.exception(f"Failed to read MinIO object: {bucket}/{object_name}")
            raise RuntimeError(f"Failed to read HTML: {e}")

        if not raw_html or len(raw_html.strip()) < 20:
            logger.warning("HTML content is empty or too small.")
            return ""

        # Primary extraction (BeautifulSoup)
        soup = BeautifulSoup(raw_html, "lxml")
        self._remove_noise_tags(soup)
        self._remove_noise_elements(soup)
        raw_text = soup.get_text(" ", strip=True)

        # Fallback using Readability if primary extraction too short
        extracted = raw_text if len(raw_text) >= 50 else self._fallback_readability(raw_html)

        # Clean extracted text
        cleaned_text = clean_text(extracted)

        logger.info(f"Extraction complete. Raw chars={len(raw_html)}, Cleaned chars={len(cleaned_text)}")
        return cleaned_text

    async def extract_and_save(
        self,
        src_bucket: str,
        html_object: str,
        dest_bucket: str,
        output_name: str,
    ) -> str:
        """
        Extract and save cleaned text to MinIO.
        Returns the cleaned text.
        """
        cleaned_text = await self.extract_from_html(src_bucket, html_object)

        try:
            await run_in_threadpool(write_object, dest_bucket, output_name, cleaned_text)
        except Exception as e:
            logger.exception(f"Failed to save extracted text to MinIO: {dest_bucket}/{output_name}")
            raise RuntimeError("Failed to save extracted text") from e

        logger.info(f"Saved extracted text to MinIO: {dest_bucket}/{output_name}")
        return cleaned_text

    # ---------------------- INTERNAL HELPERS ----------------------------

    def _fallback_readability(self, raw_html: str) -> str:
        try:
            readable = Document(raw_html)
            return readable.summary(html=False)
        except Exception:
            logger.exception("Readability fallback parsing failed.")
            return ""

    def _remove_noise_tags(self, soup: BeautifulSoup):
        noisy_tags = ["script", "style", "noscript", "svg", "img", "footer", "nav"]
        for tag in soup(noisy_tags):
            tag.decompose()


            
    def _remove_noise_elements(self, soup: BeautifulSoup):
        """
        Remove HTML elements containing noisy content (banners, popups, modals, ads, cookie notices, etc.)
        Uses a single regex for both id and class attributes to improve performance on large HTML.
        """
        noise_keywords = [
            "cookie", "popup", "modal", "banner", "footer",
            "header", "ads", "tracking", "subscribe",
            "newsletter", "consent"
        ]
        
        # Compile regex pattern to match any noise keyword
        pattern = re.compile("|".join(noise_keywords), re.IGNORECASE)

        for elem in soup.find_all(True):
            elem_id = elem.get("id", "")
            elem_classes = " ".join(elem.get("class", []))  # join class list to a single string

            # If id or class matches noise pattern, remove element
            if pattern.search(elem_id) or pattern.search(elem_classes):
                elem.decompose()
