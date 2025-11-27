"""
Text Extractor Service (Supabase Storage).

This module provides the TextExtractorService class, which handles the extraction of text
from raw content. It now manages the entire pipeline of uploading raw content
to Supabase Storage (using the configured bucket ID) and cleaning the content.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

import httpx  # Used for async Supabase Storage API calls
from readability import Document

from app.api.core.config import settings
from app.api.utils.cleaned_text import cleaned_html, normalize_text

# --- BS4 Imports with Safety Checks ---
try:
    from bs4 import BeautifulSoup, Comment

    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    Comment = None
    _HAS_BS4 = False

# --- MinIO Imports are REMOVED as requested ---
# We no longer rely on the minio SDK

logger = logging.getLogger(__name__)
EXTRACTOR_VERSION = "1.6.0 (Supabase Configured)"


class TextExtractorService:
    """
    Unified service for Supabase storage and text extraction.

    The primary bucket ID is configured via settings (e.g., 'lwd_scrape'), and
    the bucket arguments in process_pipeline are treated as folder prefixes.
    """

    def __init__(self):
        # Base Storage URL from general Supabase URL
        self.base_storage_url = f"{settings.SUPABASE_URL}/storage/v1/object"

        # Main Bucket ID from configuration (This will be 'lwd_scrape')
        self.main_bucket_id = settings.SUPABASE_STORAGE_BUCKET_ID

        # Headers include the required Service Role Key for high-privilege uploads
        self.headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/octet-stream",
        }
        self.http_client = httpx.AsyncClient()

    # --- Core Supabase Operations (Async) ---

    async def _upload_bytes_async(
        self, file_data: bytes, folder_prefix: str, object_name: str
    ) -> str:
        """
        Async upload method using httpx for Supabase Storage API.

        Constructs the URL using the main bucket ID and the folder prefix.
        Example Path: /lwg_scrape/raw-scraped-text/raw/project_id/file.html
        """

        # The final path structure combines the folder prefix and the object key
        final_object_path = f"{folder_prefix}/{object_name}"

        # Construct the full upload URL
        upload_url = f"{self.base_storage_url}/{self.main_bucket_id}/{final_object_path}"

        try:
            # Perform the PUT request to upload the file
            response = await self.http_client.put(
                upload_url, content=file_data, headers=self.headers, timeout=30.0
            )
            response.raise_for_status()  # Raise exception for 4xx or 5xx errors

            logger.info(
                f"Successfully uploaded to Supabase: {self.main_bucket_id}/{final_object_path}"
            )
            return final_object_path

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Supabase Upload HTTP Error ({e.response.status_code}): {e.response.text}"
            )
            raise Exception(f"Failed to upload to Supabase: {e.response.text}") from e
        except Exception as e:
            logger.error(f"Unexpected Supabase Upload Error: {e}")
            raise e

    # The old _upload_bytes_sync and _fetch_bytes_sync (MinIO) methods are removed.

    # --- Pipeline Methods ---

    async def process_pipeline(
        self,
        raw_content: bytes,
        raw_folder_prefix: str,  # e.g., 'raw-scraped-text'
        raw_key: str,
        clean_folder_prefix: str,  # e.g., 'cleaned-scraped-text'
        source_id: str,
        revision_id: UUID = None,
    ) -> Dict[str, Any]:
        """
        Master method for the Scraping Pipeline, using Supabase Storage.
        """
        revision_id = revision_id or uuid4()

        # 1. Upload Raw Content
        try:
            # Uploads to: lwd_scrape/raw-scraped-text/raw/project_id/...
            await self._upload_bytes_async(raw_content, raw_folder_prefix, raw_key)
        except Exception as e:
            logger.error(f"Failed to upload raw content: {e}")
            raise e

        # 2. Clean (Directly from bytes)
        extracted_text = cleaned_html(raw_content)

        # Readability Fallback
        if len(extracted_text) < 50:
            try:
                html_str = raw_content.decode("utf-8", errors="ignore")
                extracted_text = normalize_text(Document(html_str).summary(html=False))
            except Exception:
                pass

        extracted_text = normalize_text(extracted_text)

        # 3. Upload Cleaned
        clean_key_path = self._generate_clean_key(source_id, revision_id)
        if extracted_text:
            try:
                # Uploads to: lwd_scrape/cleaned-scraped-text/clean/source_id/...
                await self._upload_bytes_async(
                    extracted_text.encode("utf-8"), clean_folder_prefix, clean_key_path
                )
            except Exception as e:
                logger.warning(f"Failed to upload clean text (non-fatal): {e}")

        # 4. Return Data
        return {
            "full_text": extracted_text,
            "raw_key": raw_key,
            "clean_key": clean_key_path,
            "revision_id": str(revision_id),
            "char_count": len(extracted_text),
        }

    def _generate_clean_key(self, source_id: str, revision_id: UUID) -> str:
        """Generates a standard key for cleaned text files."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        # This path is relative to the folder prefix (e.g., 'cleaned-scraped-text')
        return f"clean/{source_id}/{timestamp}_{revision_id}.txt"

    # Legacy MinIO fetch method removed as it is no longer supported.
