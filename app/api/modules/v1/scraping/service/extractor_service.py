import logging
import re

from bs4 import BeautifulSoup
from fastapi.concurrency import run_in_threadpool
from readability import Document

from app.api.modules.v1.scraping.service.minio_client import (
    read_object,
    write_object,
    MinioReadError,
    MinioWriteError
)
from app.api.utils.response_payloads import success_response, error_response

logger = logging.getLogger(__name__)
EXTRACTOR_VERSION = "1.1.0"


def clean_text(text: str) -> str:
    """Clean extracted text by removing extra whitespace and special characters."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    return text.strip()


class TextExtractorService:
    """Async HTML text extraction pipeline with MinIO integration."""

    async def extract_from_html(self, bucket: str, object_name: str) -> str:
        logger.info(f"[Extractor v{EXTRACTOR_VERSION}] Reading HTML: {bucket}/{object_name}")

        try:
            raw_html = await run_in_threadpool(read_object, bucket, object_name)
        except FileNotFoundError:
            return error_response(message=f"Object {object_name} not found in bucket {bucket}", status_code=404)
        except MinioReadError as e:
            return error_response(message=str(e), status_code=500)
        except Exception as e:
            return error_response(message=f"Unexpected error reading HTML: {e}", status_code=500)

        if not raw_html or len(raw_html.strip()) < 20:
            logger.warning("HTML content is empty or too small.")
            return error_response(message="HTML content too small to extract", status_code=400)

        # Extract text
        soup = BeautifulSoup(raw_html, "lxml")
        self._remove_noise_tags(soup)
        self._remove_noise_elements(soup)
        raw_text = soup.get_text(" ", strip=True)
        extracted = raw_text if len(raw_text) >= 50 else self._fallback_readability(raw_html)
        cleaned_text = clean_text(extracted)

        return cleaned_text

    async def extract_and_save(self, src_bucket: str, html_object: str, dest_bucket: str, output_name: str):
        cleaned_text = await self.extract_from_html(src_bucket, html_object)

        # If extraction returned a fail_response, propagate it
        if isinstance(cleaned_text, dict) and cleaned_text.get("success") is False:
            return cleaned_text

        try:
            await run_in_threadpool(write_object, dest_bucket, output_name, cleaned_text)
        except MinioWriteError as e:
            return error_response(message=str(e), status_code=500)
        except Exception as e:
            return error_response(message=f"Unexpected error saving extracted text: {e}", status_code=500)

        logger.info(f"Saved extracted text to MinIO: {dest_bucket}/{output_name}")
        return success_response(
            status_code=200,
            message="Extraction completed",
            data={"object_name": output_name, "bucket": dest_bucket}
        )

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
            "cookie", "popup", "modal", "banner", "footer", "header", "ads", "tracking",
            "subscribe", "newsletter", "consent",
        ]
        pattern = re.compile("|".join(noise_keywords), re.IGNORECASE)

        for elem in soup.find_all(True):
            elem_id = elem.get("id", "")
            elem_classes = " ".join(elem.get("class", []))
            if pattern.search(elem_id) or pattern.search(elem_classes):
                elem.decompose()
