import logging
from datetime import datetime
from typing import Dict

from deepdiff import DeepDiff  # You need to install this: pip install deepdiff

# Services & Utils
from playwright.async_api import async_playwright
from sqlalchemy import desc

# Database & Models
from sqlalchemy.orm import Session

from app.api.core.security import decrypt_auth_details
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision_model import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult
from app.api.modules.v1.scraping.service.ai_service import AIService
from app.api.modules.v1.scraping.storage.minio_storage import upload_raw_content
from app.api.utils.text_cleaner import clean_html_content

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()

    async def execute_scrape_job(self, source_id: str) -> Dict:
        """
        Orchestrates the full pipeline:
        Fetch Config -> Scrape -> Archive -> Clean -> Analyze -> Diff -> Save
        """
        # 1. Fetch Source & Related Context (Project/Jurisdiction)
        # We need the Hierarchy to build the AI Prompts
        source = self.db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Assuming relationships are set up in SQLAlchemy models
        # Source -> Jurisdiction -> Project
        jurisdiction = self.db.query(Jurisdiction).filter(Jurisdiction.id == source.jurisdiction_id).first()
        project = self.db.query(Project).filter(Project.id == jurisdiction.project_id).first()

        # 2. Decrypt Auth Credentials (if they exist)
        auth_creds = {}
        if source.auth_details_encrypted:
            try:
                auth_creds = decrypt_auth_details(source.auth_details_encrypted)
            except Exception as e:
                logger.error(f"Auth decryption failed for source {source.id}: {e}")
                # We proceed without auth, or you could raise an error depending on strictness

        # 3. Scrape Raw Content (The Heavy I/O)
        logger.info(f"Starting Playwright scrape for: {source.url}")
        raw_html_bytes = await self._perform_browser_scrape(source.url, auth_creds)

        # 4. ARCHIVE RAW (Legal Proof)
        # Upload the "Dirty" HTML to Min.io
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        object_name = f"{source.id}/{timestamp}.html"
        
        minio_key = upload_raw_content(
            file_data=raw_html_bytes,
            bucket_name="raw-content", # Ensure this bucket exists in Minio config
            object_name=object_name
        )

        # 5. CLEANING (Token Optimization)
        # Convert HTML to clean text in-memory for the AI
        clean_text_for_ai = clean_html_content(raw_html_bytes)

        # 6. AI EXTRACTION
        # Construct the prompts from the database relationships
        # Logic: Master Prompt + (Optional) Jurisdiction Override + (Optional) Source Context
        master_prompt = project.master_prompt
        context_prompt = (jurisdiction.override_prompt or "") + " " + (source.scraping_rules.get("prompt_hint", "") if source.scraping_rules else "")
        
        logger.info(f"Sending content to AI for analysis (Length: {len(clean_text_for_ai)} chars)")
        
        ai_result_dict = await self.ai_service.generate_structured_data(
            cleaned_text=clean_text_for_ai,
            project_prompt=master_prompt,
            jurisdiction_prompt=context_prompt,
            schema=ExtractionResult,
            max_retries=3
        )

        # 7. DIFFING & CHANGE DETECTION
        # Fetch the PREVIOUS revision to compare against
        last_revision = self.db.query(DataRevision)\
            .filter(DataRevision.source_id == source.id)\
            .order_by(desc(DataRevision.scraped_at))\
            .first()

        was_change_detected = False
        
        if last_revision and last_revision.extracted_data:
            # semantic comparison ignoring order
            diff = DeepDiff(
                last_revision.extracted_data.get("extracted_data", {}), # Compare only the data payload
                ai_result_dict.get("extracted_data", {}), 
                ignore_order=True
            )
            if diff:
                was_change_detected = True
                logger.info(f"Change detected for source {source.id}")
        elif not last_revision:
            # First time scraping is always a "change" (Baseline)
            was_change_detected = True
            logger.info(f"Baseline revision created for source {source.id}")

        # 8. SAVE TO DATABASE
        new_revision = DataRevision(
            source_id=source.id,
            minio_object_key=minio_key,
            extracted_data=ai_result_dict, # Stores full JSON {summary: "...", extracted_data: {...}}
            ai_summary=ai_result_dict.get("summary"),
            was_change_detected=was_change_detected,
            scraped_at=datetime.utcnow()
        )

        self.db.add(new_revision)
        self.db.commit()
        self.db.refresh(new_revision)

        return {
            "status": "success",
            "revision_id": str(new_revision.id),
            "change_detected": was_change_detected
        }

    async def _perform_browser_scrape(self, url: str, creds: Dict) -> bytes:
        """
        Private method to handle the specific Playwright logic
        """
        async with async_playwright() as p:
            # Launch with specific arguments to avoid detection
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"] 
            )
            
            # Create a context with a realistic User Agent
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            page = await context.new_page()

            # --- Auth Handling (Simple Form Fill Example) ---
            if creds:
                # Assuming standard username/password keys. 
                # Complex sites might need custom logic per SourceType.
                if "username" in creds and "password" in creds:
                    try:
                        # You might need to navigate to a login URL first if it differs from source.url
                        # For now, we assume basic auth or landing page login
                        # await page.fill('input[name="username"]', creds['username'])
                        # await page.fill('input[name="password"]', creds['password'])
                        # await page.click('button[type="submit"]')
                        # await page.wait_for_load_state('networkidle')
                        pass
                    except Exception as e:
                        logger.warning(f"Attempted login failed: {e}")

            try:
                # Navigate and Wait
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Dynamic wait for network to settle (Critical for React/Angular apps)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.warning("Networkidle timeout, proceeding with current content")

                content = await page.content()
                return content.encode("utf-8")
            
            except Exception as e:
                logger.error(f"Playwright Scrape Failed: {e}")
                raise e # Re-raise to let the Task Retry logic handle it
            
            finally:
                await browser.close()