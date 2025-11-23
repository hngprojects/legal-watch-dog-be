import logging
import re

from bs4 import BeautifulSoup
from fastapi.concurrency import run_in_threadpool
from readability import Document

from app.api.modules.v1.scraping.service.minio_client import read_object, write_object

logger = logging.getLogger(__name__)
EXTRACTOR_VERSION = "1.1.0"


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    return text.strip()


class TextExtractorService:
    """Async HTML text extraction pipeline with MinIO integration."""

    async def extract_from_html(self, bucket: str, object_name: str) -> str:
        """Return extracted text from HTML stored in MinIO."""
        logger.info(f"[Extractor v{EXTRACTOR_VERSION}] Reading HTML: {bucket}/{object_name}")
        raw_html = await run_in_threadpool(read_object, bucket, object_name)

        if not raw_html or len(raw_html.strip()) < 20:
            logger.warning("HTML content is empty or too small.")
            return ""

        # Extract text
        soup = BeautifulSoup(raw_html, "lxml")
        self._remove_noise_tags(soup)
        self._remove_noise_elements(soup)
        raw_text = soup.get_text(" ", strip=True)
        extracted = raw_text if len(raw_text) >= 50 else self._fallback_readability(raw_html)
        cleaned_text = clean_text(extracted)
        return cleaned_text

    async def extract_and_save(
        self, src_bucket: str, html_object: str, dest_bucket: str, output_name: str
    ) -> dict:
        """
        Extract text from HTML in MinIO, save to MinIO, and return metadata.
        """
        cleaned_text = await self.extract_from_html(src_bucket, html_object)

        # If extraction failed (empty text)
        if not cleaned_text:
            return {
                "success": False,
                "message": f"No text extracted from '{html_object}'",
                "status_code": 400,
                "data": {},
            }

        # Save to MinIO
        await run_in_threadpool(write_object, dest_bucket, output_name, cleaned_text)

        return {
            "success": True,
            "message": "Extraction completed",
            "status_code": 200,
            "data": {
                "object_name": output_name,
                "bucket": dest_bucket,
                "text_preview": cleaned_text[:500],  # first 200 chars
            },
        }

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
        for tag in soup.find_all(noisy_tags):
            tag.decompose()

    def _remove_noise_elements(self, soup: BeautifulSoup):
        noise_keywords = [
            "cookie",
            "popup",
            "modal",
            "banner",
            "footer",
            "header",
            "ads",
            "tracking",
            "subscribe",
            "newsletter",
            "consent",
        ]
        pattern = re.compile("|".join(noise_keywords), re.IGNORECASE)
        for elem in soup.find_all(True):
            elem_id = elem.get("id", "")
            elem_classes = " ".join(elem.get("class", []))
            if pattern.search(elem_id) or pattern.search(elem_classes):
                elem.decompose()
