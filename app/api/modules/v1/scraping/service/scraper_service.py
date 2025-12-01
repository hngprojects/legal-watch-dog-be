"""Service for orchestrating the web scraping pipeline.

Handles the end-to-end flow of fetching content, extracting text,
analyzing with AI, detecting changes, and persisting data revisions.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select

from app.api.core.security import decrypt_auth_details
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.service.revision_notification_task import (
    send_revision_notifications_task,
)
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.cloudscrapper_service import HTTPClientService
from app.api.modules.v1.scraping.service.diff_service import DiffAIService
from app.api.modules.v1.scraping.service.extractor_service import TextExtractorService
from app.api.modules.v1.scraping.service.llm_service import AIExtractionService
from app.api.modules.v1.scraping.service.pdf_service import PDFService

logger = logging.getLogger(__name__)


class ScraperService:
    """Orchestrates the scraping, extraction, and analysis pipeline."""

    def __init__(self, db: AsyncSession):
        """Initialize the ScraperService with necessary dependencies.

        Args:
            db (AsyncSession): The asynchronous database session.
        """
        self.db = db
        self.ai_extractor = AIExtractionService()
        self.text_extractor = TextExtractorService()
        self.differ = DiffAIService()
        self.http_client = HTTPClientService()
        self.pdf_service = PDFService()

    async def execute_scrape_job(self, source_id: str) -> Dict[str, Any]:
        """Execute the full scraping pipeline for a given source.

        Fetching -> Archiving -> Cleaning -> Hashing -> AI Extraction -> Diffing -> Persistence.
        If a change is detected AND it is not the first run, it triggers a notification.

        Args:
            source_id (str): The UUID of the source to scrape.

        Returns:
            Dict[str, Any]: A summary of the scrape execution including status and changes.

        Raises:
            ValueError: If the source ID cannot be found.
            Exception: Propagates any errors occurring during the pipeline.
        """
        logger.info(f"Starting pipeline for Source ID: {source_id}")

        query = (
            select(Source)
            .where(Source.id == source_id)
            .options(selectinload(Source.jurisdiction).selectinload(Jurisdiction.project))
        )
        result = await self.db.execute(query)
        source = result.scalars().first()

        if not source:
            raise ValueError(f"Source {source_id} not found")

        jurisdiction = source.jurisdiction
        project = jurisdiction.project

        auth_creds = {}
        if source.auth_details_encrypted:
            try:
                auth_creds = decrypt_auth_details(source.auth_details_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt auth details: {e}")

        if source.url.startswith("mock://"):
            mock_html = source.scraping_rules.get("mock_html", "<html></html>")
            raw_content_bytes = mock_html.encode("utf-8")
            logger.info(f"Using mock HTML for {source.name}")
            content_type = "text/html"
        else:
            raw_content_bytes = await self.http_client.fetch_content(source.url, auth_creds)
            content_type = source.scraping_rules.get("expected_type", "text/html").lower()

        is_pdf = self.pdf_service.is_pdf(raw_content_bytes, content_type)
        if is_pdf:
            logger.info("PDF detected. Extracting text...")
            try:
                text_content = self.pdf_service.extract_text(raw_content_bytes)
                raw_content_bytes = f"<html><body><pre>{text_content}</pre></body></html>".encode(
                    "utf-8"
                )
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                raw_content_bytes = b"<html><body>PDF extraction failed</body></html>"

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        raw_minio_key = f"raw/{project.id}/{source.id}/{timestamp_str}.html"

        extraction_result = await self.text_extractor.process_pipeline(
            raw_content=raw_content_bytes,
            raw_bucket="raw-content",
            raw_key=raw_minio_key,
            clean_bucket="clean-content",
            source_id=source.id,
        )

        clean_text = extraction_result["full_text"]
        content_hash = hashlib.sha256(clean_text.encode()).hexdigest()

        rev_query = (
            select(DataRevision)
            .where(DataRevision.source_id == source.id)
            .order_by(desc(DataRevision.scraped_at))
            .limit(1)
        )
        rev_result = await self.db.execute(rev_query)
        last_revision = rev_result.scalars().first()

        diff_patch = {}
        was_change_detected = False

        if last_revision and last_revision.content_hash == content_hash:
            logger.info(f"Content unchanged (hash: {content_hash[:8]}...). Skipping AI.")
            ai_result = last_revision.extracted_data
            diff_patch = {"change_summary": "No material changes detected", "risk_level": "NONE"}
        else:
            logger.info("Content changed. Running AI Extraction...")

            master_prompt = project.master_prompt
            context_prompt = jurisdiction.prompt or ""

            ai_result = await self.ai_extractor.run_llm_analysis(
                cleaned_text=clean_text,
                project_prompt=master_prompt,
                jurisdiction_prompt=context_prompt,
            )

            old_data = (
                last_revision.extracted_data.get("extracted_data", {}) if last_revision else {}
            )
            new_data = ai_result.get("extracted_data", {})

            monitoring_goal = f"{master_prompt}. Context: {context_prompt}"

            change_result = await self.differ.detect_semantic_change(
                old_data=old_data, new_data=new_data, monitoring_instruction=monitoring_goal
            )

            was_change_detected = change_result.has_changed
            if was_change_detected:
                logger.info(f"Change Detected: {change_result.change_summary}")
                diff_patch = {
                    "change_summary": change_result.change_summary,
                    "risk_level": change_result.risk_level,
                }
            else:
                diff_patch = {
                    "change_summary": "No material changes detected",
                    "risk_level": "NONE",
                }

        try:
            new_revision = DataRevision(
                source_id=source.id,
                minio_object_key=extraction_result["raw_key"],
                content_hash=content_hash,
                extracted_data=ai_result,
                ai_summary=ai_result.get("summary"),
                ai_markdown_summary=ai_result.get("markdown_summary"),
                ai_confidence_score=ai_result.get("confidence_score"),
                was_change_detected=was_change_detected,
                scraped_at=datetime.utcnow(),
            )
            self.db.add(new_revision)
            await self.db.flush()

            if was_change_detected and last_revision:
                new_diff_record = ChangeDiff(
                    new_revision_id=new_revision.id,
                    old_revision_id=last_revision.id,
                    diff_patch=diff_patch,
                    ai_confidence=ai_result.get("confidence_score", 0.0),
                )
                self.db.add(new_diff_record)

            await self.db.commit()
            await self.db.refresh(new_revision)

            if was_change_detected and last_revision:
                logger.info(f"Triggering notifications for revision {new_revision.id}")
                send_revision_notifications_task.delay(str(new_revision.id))
            elif was_change_detected and not last_revision:
                logger.info(f"First scrape for source {source.id}. Skipping notification.")

        except Exception as e:
            await self.db.rollback()
            raise e

        return {
            "status": "success",
            "change_detected": was_change_detected,
            "change_summary": diff_patch.get("change_summary"),
        }
