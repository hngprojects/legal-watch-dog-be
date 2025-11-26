import hashlib
import logging
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select

from app.api.core.security import decrypt_auth_details
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.cloudscrapper_service import HTTPClientService
from app.api.modules.v1.scraping.service.diff_service import DiffAIService
from app.api.modules.v1.scraping.service.extractor_service import TextExtractorService

# Service Imports
from app.api.modules.v1.scraping.service.llm_service import AIExtractionService
from app.api.modules.v1.scraping.service.pdf_service import PDFService

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self, db: AsyncSession):
        """
        Initializes the service with an ASYNC database session.
        """
        self.db = db
        # AIExtractionService is initialized here to process cleaned text
        self.ai_extractor = AIExtractionService()
        self.text_extractor = TextExtractorService()  # Handles Upload + Cleaning
        self.differ = DiffAIService()
        self.http_client = HTTPClientService()
        self.pdf_service = PDFService()

    async def execute_scrape_job(self, source_id: str) -> Dict[str, Any]:
        """
        Orchestrates the scraping pipeline:
        Fetch -> Archive(Raw) -> Clean -> Archive(Clean) -> Hash -> AI Extract -> Diff -> Alert.
        """
        logger.info(f"Starting pipeline for Source ID: {source_id}")

        # 1. Fetch Source & Eagerly Load Relationships
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

        # 2. Handle Auth Credentials
        auth_creds = {}
        if source.auth_details_encrypted:
            try:
                auth_creds = decrypt_auth_details(source.auth_details_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt auth details: {e}")

        # 3. Fetch Content (Mock or Real)
        if source.url.startswith("mock://"):
            mock_html = source.scraping_rules.get("mock_html", "<html></html>")
            raw_content_bytes = mock_html.encode("utf-8")
            logger.info(f"Using mock HTML for {source.name}")
            content_type = "text/html"
        else:
            raw_content_bytes = await self.http_client.fetch_content(source.url, auth_creds)
            content_type = source.scraping_rules.get("expected_type", "text/html").lower()

        # 4. PDF Handling
     
        is_pdf = self.pdf_service.is_pdf(raw_content_bytes, content_type)
        if is_pdf:
            logger.info("PDF detected. Extracting text...")
            try:
                text_content = self.pdf_service.extract_text(raw_content_bytes)
                # Wrap in fake HTML structure
                raw_content_bytes = f"<html><body><pre>{text_content}</pre></body></html>".encode(
                    "utf-8"
                )
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                raw_content_bytes = b"<html><body>PDF extraction failed</body></html>"

        # 5. Pipeline: Upload Raw -> Clean -> Upload Clean
        # We generate a Raw Key here to pass to the extractor
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        raw_minio_key = f"raw/{project.id}/{source.id}/{timestamp_str}.html"

        # Execute the unified extraction pipeline
        extraction_result = await self.text_extractor.process_pipeline(
            raw_content=raw_content_bytes,
            raw_bucket="raw-content",
            raw_key=raw_minio_key,
            clean_bucket="clean-content",
            source_id=source.id,
        )

        clean_text = extraction_result["full_text"]

        # 6. Hash Check
        content_hash = hashlib.sha256(clean_text.encode()).hexdigest()

        # Fetch Last Revision (Async)
        rev_query = (
            select(DataRevision)
            .where(DataRevision.source_id == source.id)
            .order_by(desc(DataRevision.scraped_at))
            .limit(1)
        )
        rev_result = await self.db.execute(rev_query)
        last_revision = rev_result.scalars().first()

        # 7. Content Change Gatekeeper
        diff_patch = {}
        was_change_detected = False

        # If content hasn't changed, skip the expensive AI steps
        if last_revision and last_revision.content_hash == content_hash:
            logger.info(f"Content unchanged (hash: {content_hash[:8]}...). Skipping AI.")
            ai_result = last_revision.extracted_data
            diff_patch = {"change_summary": "No material changes detected", "risk_level": "NONE"}
        else:
            # 8. AI Extraction
            # We pass the clean text we just got from text_extractor
            logger.info("Content changed. Running AI Extraction...")

            master_prompt = project.master_prompt
            context_prompt = jurisdiction.prompt or ""

            ai_result = await self.ai_extractor.run_llm_analysis(
                cleaned_text=clean_text,
                project_prompt=master_prompt,
                jurisdiction_prompt=context_prompt,
            )

            # 9. AI Semantic Diff
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

        # 10. Async Persistence
        try:
            new_revision = DataRevision(
                source_id=source.id,
                minio_object_key=extraction_result["raw_key"],  # Key for Raw HTML
                # You might want to save the clean key too if your model supports it:
                # clean_object_key=extraction_result["clean_key"],
                content_hash=content_hash,
                extracted_data=ai_result,
                ai_summary=ai_result.get("summary"),
                ai_markdown_summary=ai_result.get("markdown_summary"),
                ai_confidence_score=ai_result.get("confidence_score"),
                was_change_detected=was_change_detected,
                scraped_at=datetime.utcnow(),
            )
            self.db.add(new_revision)

            # Flush to get ID for diff record
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

        except Exception as e:
            await self.db.rollback()
            raise e

        return {
            "status": "success",
            "change_detected": was_change_detected,
            "change_summary": diff_patch.get("change_summary"),
        }
