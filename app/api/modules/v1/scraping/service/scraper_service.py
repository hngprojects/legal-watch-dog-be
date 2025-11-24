import logging
from datetime import datetime
from typing import Dict, Any

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
from app.api.modules.v1.notifications.service.notification_tasks import send_change_alert

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = AIExtractionService() 
        self.differ = DiffAIService()          
        self.browser = PlaywrightService()

    async def execute_scrape_job(self, source_id: str) -> Dict[str, Any]:
        logger.info(f"Starting pipeline for Source ID: {source_id}")

        # 1-5. [Context, Auth, Scrape, Archive, Clean] (Same as previous)
        source = self.db.query(Source).filter(Source.id == source_id).first()
        jurisdiction = self.db.query(Jurisdiction).filter(Jurisdiction.id == source.jurisdiction_id).first()
        project = self.db.query(Project).filter(Project.id == jurisdiction.project_id).first()
        
        auth_creds = {}
        if source.auth_details_encrypted:
            try:
                auth_creds = decrypt_auth_details(source.auth_details_encrypted)
            except Exception:
                pass

        raw_html_bytes = await self.browser.scrape(source.url, auth_creds)
        
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        minio_key = f"raw/{project.id}/{source.id}/{timestamp_str}.html"
        upload_raw_content(raw_html_bytes, "raw-content", minio_key)
        
        clean_text = clean_html_content(raw_html_bytes)

        # --- 6. AI EXTRACTION (Using ExtractionService) ---
        master_prompt = project.master_prompt
        context_prompt = (jurisdiction.override_prompt or "")
        
        ai_result = await self.extractor.generate_structured_data(
            cleaned_text=clean_text,
            project_prompt=master_prompt,
            jurisdiction_prompt=context_prompt
        )

        # --- 7. CHANGE DETECTION (Using DiffService -> DiffAIService) ---
        last_revision = self.db.query(DataRevision)\
            .filter(DataRevision.source_id == source.id)\
            .order_by(desc(DataRevision.scraped_at))\
            .first()

        old_data = last_revision.extracted_data.get("extracted_data", {}) if last_revision else {}
        new_data = ai_result.get("extracted_data", {})
        diff_context = f"Project Goal: {project.master_prompt}"

        was_change_detected, diff_patch = await self.differ.compute_diff(
            old_data=old_data,
            new_data=new_data,
            context=diff_context
        )

        if was_change_detected:
            logger.info(f"Change Detected: {diff_patch.get('change_summary')}")

        # 8. PERSISTENCE
        try:
            new_revision = DataRevision(
                source_id=source.id,
                minio_object_key=minio_key,
                extracted_data=ai_result,
                ai_summary=ai_result.get("summary"),
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
            send_change_alert.delay(str(new_revision.id))

        return {"status": "success", "change_detected": was_change_detected}

    # Browser scraping is now provided by `PlaywrightService.scrape`