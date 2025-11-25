import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select, desc

from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction

# Service Imports
from app.api.modules.v1.scraping.service.ai_extraction_service import AIExtractionService
from app.api.modules.v1.scraping.service.diff_service import DiffAIService
from app.api.modules.v1.scraping.service.pdf_service import PDFService
from app.api.modules.v1.scraping.service.http_client_service import HTTPClientService
from app.api.modules.v1.scraping.storage.minio_storage import upload_raw_content
from app.api.utils.text_cleaner import clean_html_content
from app.api.core.security import decrypt_auth_details

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self, db: AsyncSession):
        """
        Initializes the service with an ASYNC database session.
        """
        self.db = db
        self.extractor = AIExtractionService()
        self.differ = DiffAIService()
        self.http_client = HTTPClientService()
        self.pdf_service = PDFService()

    async def execute_scrape_job(self, source_id: str) -> Dict[str, Any]:
        """
        Orchestrates the scraping pipeline:
        Fetch -> Archive -> Clean -> AI Extract -> Diff -> Alert.
        """
        logger.info(f"Starting pipeline for Source ID: {source_id}")

        # 1. Fetch Source & Eagerly Load Relationships
        # NOTE: In Async, we MUST use selectinload because lazy loading is disabled.
        query = (
            select(Source)
            .where(Source.id == source_id)
            .options(
                selectinload(Source.jurisdiction).selectinload(Jurisdiction.project)
            )
        )
        result = await self.db.execute(query)
        source = result.scalars().first()

        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Access loaded relationships safely
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
            raw_content_bytes = mock_html.encode('utf-8')
            content_type = 'text/html'
            logger.info(f"Using mock HTML for {source.name}")
        else:
            # http_client is already async
            raw_content_bytes = await self.http_client.fetch_content(source.url, auth_creds)
            content_type = source.scraping_rules.get("expected_type", "text/html").lower()

        # 4. PDF Handling
        is_pdf = self.pdf_service.is_pdf(raw_content_bytes, content_type)
        if is_pdf:
            logger.info(f"PDF detected. Extracting text...")
            try:
                # PDF service is typically CPU bound, might want to run in thread if heavy
                text_content = self.pdf_service.extract_text(raw_content_bytes)
                # Wrap in HTML for consistent processing
                raw_html_bytes = f"<html><body><pre>{text_content}</pre></body></html>".encode('utf-8')
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                raw_html_bytes = b"<html><body>PDF extraction failed</body></html>"
        else:
            raw_html_bytes = raw_content_bytes

        # 5. Archive to MinIO (Blocking I/O - assuming library handles it or it's fast enough)
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        minio_key = f"raw/{project.id}/{source.id}/{timestamp_str}.html"
        
        # Ideally, make upload_raw_content async or wrap in asyncio.to_thread
        # await asyncio.to_thread(upload_raw_content, raw_html_bytes, "raw-content", minio_key)
        upload_raw_content(raw_html_bytes, "raw-content", minio_key)

        # 6. Clean Text & Hash Check
        clean_text = clean_html_content(raw_html_bytes)
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
        if last_revision and last_revision.content_hash == content_hash:
            logger.info(f"Content unchanged (hash: {content_hash[:8]}...). Skipping AI.")
            ai_result = last_revision.extracted_data
            was_change_detected = False
            diff_patch = {"change_summary": "No material changes detected", "risk_level": "NONE"}
        else:
            # 8. AI Extraction
            master_prompt = project.master_prompt
            context_prompt = (jurisdiction.prompt or "")
            
            ai_result = await self.extractor.run_llm_analysis(
                cleaned_text=clean_text,
                project_prompt=master_prompt,
                jurisdiction_prompt=context_prompt
            )

            # 9. AI Semantic Diff
            old_data = last_revision.extracted_data.get("extracted_data", {}) if last_revision else {}
            new_data = ai_result.get("extracted_data", {})
            
            # Construct strict monitoring instruction
            monitoring_goal = f"{master_prompt}. Context: {context_prompt}"

            change_result = await self.differ.detect_semantic_change(
                old_data=old_data,
                new_data=new_data,
                monitoring_instruction=monitoring_goal
            )

            was_change_detected = change_result.has_changed
            if was_change_detected:
                logger.info(f"Change Detected: {change_result.change_summary}")
                diff_patch = {
                    "change_summary": change_result.change_summary,
                    "risk_level": change_result.risk_level
                }
            else:
                diff_patch = {"change_summary": "No material changes detected", "risk_level": "NONE"}

        # 10. Async Persistence
        try:
            new_revision = DataRevision(
                source_id=source.id,
                minio_object_key=minio_key,
                content_hash=content_hash,
                extracted_data=ai_result,
                ai_summary=ai_result.get("summary"),
                ai_markdown_summary=ai_result.get("markdown_summary"),
                ai_confidence_score=ai_result.get("confidence_score"),
                was_change_detected=was_change_detected,
                scraped_at=datetime.utcnow()
            )
            self.db.add(new_revision)
            
            # Flush to get ID for diff record
            await self.db.flush()

            if was_change_detected and last_revision:
                new_diff_record = ChangeDiff(
                    new_revision_id=new_revision.id,
                    old_revision_id=last_revision.id,
                    diff_patch=diff_patch,
                    ai_confidence=ai_result.get("confidence_score", 0.0)
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
            "change_summary": diff_patch.get("change_summary")
        }