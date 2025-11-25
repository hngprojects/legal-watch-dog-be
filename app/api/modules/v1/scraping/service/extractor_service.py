import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

try:
    from bs4 import BeautifulSoup, Comment

    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    Comment = None
    _HAS_BS4 = False

from fastapi.concurrency import run_in_threadpool
from readability import Document

from app.api.modules.v1.scraping.service.minio_client import (
    fetch_raw_content_from_minio,
    upload_raw_content,
)
from app.api.utils.cleaned_text import cleaned_html, normalize_text

logger = logging.getLogger(__name__)
EXTRACTOR_VERSION = "1.3.0"


class TextExtractorService:
    async def extract_from_minio(self, bucket: str, object_name: str) -> str:
        html_bytes = await run_in_threadpool(fetch_raw_content_from_minio, object_name, bucket)

        if not html_bytes or len(html_bytes.strip()) < 20:
            logger.warning(
                f"[Extractor v{EXTRACTOR_VERSION}] Raw HTML too small or empty:"
                f"{bucket}/{object_name}"
            )
            return ""

        extracted = cleaned_html(html_bytes)

        if len(extracted) < 50:
            html_str = html_bytes.decode("utf-8", errors="ignore")
            try:
                extracted = Document(html_str).summary(html=False)
                extracted = normalize_text(extracted)
            except Exception:
                logger.exception("Readability fallback failed.")

        return normalize_text(extracted)

    async def extract_and_upload(
        self,
        src_bucket: str,
        html_object: str,
        dest_bucket: str,
        source_id: UUID,
        revision_id: UUID = None,
    ) -> dict:
        revision_id = revision_id or uuid4()
        minio_object_key = self._generate_minio_key(source_id, revision_id)

        cleaned_text = await self.extract_from_minio(src_bucket, html_object)

        if not cleaned_text:
            return {
                "success": False,
                "message": f"No text extracted from '{html_object}'",
                "status_code": 400,
                "data": {},
            }

        try:
            await run_in_threadpool(
                upload_raw_content, cleaned_text.encode("utf-8"), dest_bucket, minio_object_key
            )
        except Exception as e:
            logger.error(f"Upload to MinIO failed: {e}")
            return {
                "success": False,
                "message": f"Failed to upload extracted text: {str(e)}",
                "status_code": 500,
                "data": {},
            }

        return {
            "success": True,
            "message": "Extraction and upload completed",
            "status_code": 200,
            "data": {
                "revision_id": str(revision_id),
                "source_id": str(source_id),
                "minio_object_key": minio_object_key,
                "preview": cleaned_text[:500],
                "char_count": len(cleaned_text),
            },
        }

    def _generate_minio_key(self, source_id: UUID, revision_id: UUID) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"clean/{source_id}/{timestamp}_{revision_id}.txt"
