import logging
from datetime import datetime
from typing import Dict, Any
import hashlib
import io
import tempfile

import cloudscraper
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from app.api.modules.v1.scraping.service.playwright_service import PlaywrightService
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction


from app.api.modules.v1.scraping.service.ai_extraction_service import AIExtractionService
from app.api.modules.v1.scraping.service.diff_service import DiffAIService
from app.api.modules.v1.scraping.storage.minio_storage import upload_raw_content
from app.api.utils.text_cleaner import clean_html_content
from app.api.core.security import decrypt_auth_details
# from app.api.modules.v1.notifications.service.notification_tasks import send_change_alert

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = AIExtractionService() 
        self.differ = DiffAIService()          
        self.browser = PlaywrightService()
        self.scraper = cloudscraper.create_scraper() 

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes using pdfplumber.
        
        Args:
            pdf_bytes: Raw PDF content as bytes
            
        Returns:
            Extracted text from all PDF pages joined together
            
        Raises:
            ValueError: If pdfplumber not installed or PDF is invalid
        """
        if pdfplumber is None:
            raise ValueError("pdfplumber not installed. Install with: pip install pdfplumber")
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                tmp_path = tmp.name
            
            extracted_text = []
            with pdfplumber.open(tmp_path) as pdf:
                logger.info(f"PDF has {len(pdf.pages)} pages")
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        extracted_text.append(text)
                    logger.debug(f"  Page {page_num}: {len(text)} chars extracted")
            
            return "\n\n".join(extracted_text)
        except Exception as e:
            logger.error(f"Failed to extract PDF: {type(e).__name__}: {e}")
            raise ValueError(f"PDF extraction failed: {e}")

    async def _fetch_url_content(self, url: str, auth_creds: dict) -> bytes:
        """
        Fetch URL content with CloudFlare bypass support.
        Handles both HTML and PDF responses.
        
        Args:
            url: URL to fetch
            auth_creds: Authentication credentials if needed
            
        Returns:
            Raw content as bytes (HTML or PDF)
            
        Raises:
            Exception: If fetch fails
        """
        try:
            response = self.scraper.get(url, timeout=30)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            logger.info(f"Fetched {url} - Content-Type: {content_type}")
            
            return response.content
        except Exception as e:
            logger.warning(f"cloudscraper failed: {e}. Falling back to Playwright.")
            # Fallback to Playwright for JavaScript-heavy sites
            return await self.browser.scrape(url, auth_creds)

    async def execute_scrape_job(self, source_id: str) -> Dict[str, Any]:
        logger.info(f"Starting pipeline for Source ID: {source_id}")

        # 1-5. [Context, Auth, Scrape, Archive, Clean]
        source = self.db.query(Source).filter(Source.id == source_id).first()
        jurisdiction = self.db.query(Jurisdiction).filter(Jurisdiction.id == source.jurisdiction_id).first()
        project = self.db.query(Project).filter(Project.id == jurisdiction.project_id).first()
        
        auth_creds = {}
        if source.auth_details_encrypted:
            try:
                auth_creds = decrypt_auth_details(source.auth_details_encrypted)
            except Exception:
                pass

        # Handle mock sources for testing
        if source.url.startswith("mock://"):
            mock_html = source.scraping_rules.get("mock_html", "<html></html>")
            raw_content_bytes = mock_html.encode('utf-8')
            content_type = 'text/html'
            logger.info(f"Using mock HTML for {source.name}")
        else:
            raw_content_bytes = await self._fetch_url_content(source.url, auth_creds)
            content_type = source.scraping_rules.get("expected_type", "text/html").lower()
        
        # Determine if content is PDF and extract text if needed
        is_pdf = content_type.find('pdf') >= 0 or (raw_content_bytes[:4] == b'%PDF')
        if is_pdf:
            logger.info(f"PDF detected. Extracting text...")
            try:
                text_content = self._extract_pdf_text(raw_content_bytes)
                # Convert extracted text to HTML for consistency with existing pipeline
                raw_html_bytes = f"<html><body><pre>{text_content}</pre></body></html>".encode('utf-8')
                logger.info(f"Successfully extracted {len(text_content)} chars from PDF")
            except Exception as e:
                logger.error(f"PDF extraction failed: {e}")
                raw_html_bytes = b"<html><body>PDF extraction failed</body></html>"
        else:
            raw_html_bytes = raw_content_bytes
        
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        minio_key = f"raw/{project.id}/{source.id}/{timestamp_str}.html"
        upload_raw_content(raw_html_bytes, "raw-content", minio_key)
        
        clean_text = clean_html_content(raw_html_bytes)

        # --- CHECK FOR DUPLICATE CONTENT (skip re-extraction if identical) ---
        content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
        last_revision = self.db.query(DataRevision)\
            .filter(DataRevision.source_id == source.id)\
            .order_by(desc(DataRevision.scraped_at))\
            .first()
        
        if last_revision and last_revision.content_hash == content_hash:
            logger.info(f"Content unchanged (hash: {content_hash[:8]}...). Reusing previous extraction.")
            ai_result = last_revision.extracted_data
            was_change_detected = False
            diff_patch = {"change_summary": "No material changes detected", "risk_level": "NONE"}
        else:
            # --- 6. AI EXTRACTION (Using ExtractionService) ---
            master_prompt = project.master_prompt
            context_prompt = (jurisdiction.prompt or "")
            
            ai_result = await self.extractor.generate_structured_data(
                cleaned_text=clean_text,
                project_prompt=master_prompt,
                jurisdiction_prompt=context_prompt
            )

            # --- 7. CHANGE DETECTION (Using DiffService -> DiffAIService) ---
            old_data = last_revision.extracted_data.get("extracted_data", {}) if last_revision else {}
            new_data = ai_result.get("extracted_data", {})
            diff_context = f"Project Goal: {project.master_prompt}"

            change_result = await self.differ.detect_semantic_change(
                old_data=old_data,
                new_data=new_data,
                context=diff_context
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

        # 8. PERSISTENCE
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
            self.db.flush()

            if was_change_detected and last_revision:
                new_diff_record = ChangeDiff(
                    new_revision_id=new_revision.id,
                    old_revision_id=last_revision.id,
                    diff_patch=diff_patch,
                    ai_confidence=ai_result.get("confidence_score", 0.0)
                )
                self.db.add(new_diff_record)

            self.db.commit()
            self.db.refresh(new_revision)

        except Exception as e:
            self.db.rollback()
            raise e

        # 9. ALERTING
        if was_change_detected and last_revision: 
            logger.info(f"Change detected for source {source_id}: {diff_patch['change_summary']}")
            return {
                "status": "success",
                "change_detected": True,
                "change_summary": diff_patch["change_summary"],
                "risk_level": diff_patch["risk_level"],
                "ai_summary": ai_result.get("summary"),
                "ai_markdown_summary": ai_result.get("markdown_summary"),
                "ai_confidence_score": ai_result.get("confidence_score"),
            }
        #     send_change_alert.delay(str(new_revision.id))

        return {"status": "success", "change_detected": was_change_detected}

