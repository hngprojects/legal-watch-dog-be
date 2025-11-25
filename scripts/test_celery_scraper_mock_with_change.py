"""
Mock Celery Worker Test: Scraper Service Pipeline with Change Detection

Simulates the actual Celery worker flow with mock data:
1. First run: Mock scrape with initial data → Extract → Store DataRevision (New Record)
2. Second run: Mock scrape with changed data → Extract → Detect Changes → Store Diff

Validates that:
- Extraction works with mock data
- Change detection flags work correctly when data changes
- Diff records are created properly
"""

import asyncio
import json
import sys
import traceback
from pathlib import Path
from datetime import datetime, timezone 
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select, delete
from sqlalchemy import desc

from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.scraping.models.source_model import Source, SourceType, ScrapeFrequency
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.core.config import settings

# --- CONFIGURATION ---
# Set to False if you want to verify the data in your DB tool (pgAdmin/DBeaver)
# Set to True to keep your DB clean after running tests
CLEANUP_ON_EXIT = False 

# Global setup for test data (uses asyncpg for async db access)
db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- HELPER FUNCTIONS ---

async def create_test_entities(db_session: AsyncSession, initial_mock_html: str):
    """Creates Organization, Project, Jurisdiction, and Source for the mock test."""
    
    org = Organization(id=uuid4(), name="UK Government Test Org", email="test@gov.uk", is_verified=True)
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    project = Project(
        id=uuid4(),
        org_id=org.id,
        title="UK Minimum Wage Compliance",
        master_prompt="Extract the current National Minimum Wage and National Living Wage rates per hour. Group the rates by age category (e.g., '21 and over', '18 to 20'). Identify the 'Effective Date' for these rates.",
        description="Monitor UK minimum wage rates for compliance"
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    jurisdiction = Jurisdiction(
        id=uuid4(),
        project_id=project.id,
        name="United Kingdom",
        description="UK minimum wage regulations",
        prompt="Context: HM Revenue & Customs (HMRC) official rates for the UK."
    )
    db_session.add(jurisdiction)
    await db_session.commit()
    await db_session.refresh(jurisdiction)

    source = Source(
        id=uuid4(),
        jurisdiction_id=jurisdiction.id,
        name="GOV.UK National Minimum Wage (Mock)",
        url="mock://gov.uk/national-minimum-wage-rates",
        source_type=SourceType.WEB,
        scrape_frequency=ScrapeFrequency.WEEKLY,
        next_scrape_time=datetime.now(timezone.utc),
        scraping_rules={
            "mock_html": initial_mock_html,
            "expected_type": "text/html"
        }
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    
    print(f"  [OK] Source created: {source.id}")
    return source, org, project, jurisdiction


async def run_single_scrape(db_session: AsyncSession, source_id: str, timeout: float = 120.0, scrape_num: int = 1):
    """Executes a single scrape job and returns the latest revision."""
    print(f"[WORKER-{scrape_num}] Initializing ScraperService...")
    scraper_service = ScraperService(db_session)
    print("[OK] ScraperService initialized")

    print(f"[WORKER-{scrape_num}] Executing scrape job for source: {source_id}")
    try:
        result = await asyncio.wait_for(
            scraper_service.execute_scrape_job(source_id),
            timeout=timeout
        )
        print(f"[OK] Scrape job completed (Result: {result})")
    except asyncio.TimeoutError:
        print(f"[ERROR] Scrape job timed out after {timeout} seconds")
        return None

    # Fetch the latest revision (Async Query)
    query_rev = select(DataRevision).where(
        DataRevision.source_id == source_id
    ).order_by(desc(DataRevision.scraped_at))
    
    result_rev = await db_session.execute(query_rev)
    revision = result_rev.scalars().first()
    
    if revision:
        print(f"  [OK] DataRevision created: {revision.id}")
        print(f"    Was Change Detected: {revision.was_change_detected}")
    else:
        print("[ERROR] No DataRevision created!")

    return revision


async def mock_celery_scraper_worker():
    """
    Runs the change detection test scenario using mock HTML.
    """
    test_passed = False

    # Mock initial data (April 2025 rates)
    initial_mock_html = """
    <html><body>
    <h1>National Minimum Wage and National Living Wage rates</h1>
    <table>
    <tr><th>Age</th><th>Rate from April 2025</th></tr>
    <tr><td>21 and over (National Living Wage)</td><td>£12.21</td></tr>
    <tr><td>18 to 20</td><td>£10.00</td></tr>
    </table>
    <p>These rates apply from April 2025.</p>
    </body></html>
    """

    # Updated mock data with rate changes (November 2025 rates)
    updated_mock_html = """
    <html><body>
    <h1>National Minimum Wage and National Living Wage rates</h1>
    <table>
    <tr><th>Age</th><th>Rate from November 2025</th></tr>
    <tr><td>21 and over (National Living Wage)</td><td>£12.75</td></tr>
    <tr><td>18 to 20</td><td>£10.50</td></tr>
    </table>
    <p>These rates apply from November 2025.</p>
    </body></html>
    """
    
    print("=" * 80)
    print("MOCK CELERY WORKER: Scraper Service Pipeline with Change Detection")
    print("=" * 80)
    print()
    print("[SETUP] Initializing Async Database Session...")
    
    async with AsyncSessionLocal() as db_session:
        try:
            # Create test data and mock source
            source, _, _, _ = await create_test_entities(db_session, initial_mock_html)
            source_id = str(source.id)
            print()

            # --- RUN 1: Initial Scrape (Mock April 2025) ---
            print("-" * 80)
            print("[RUN 1] Initial Extraction (April 2025 Rates)")
            print("-" * 80)
            revision1 = await run_single_scrape(db_session, source_id, scrape_num=1, timeout=60.0)
            if not revision1: return False
            
            # --- VALIDATION 1 ---
            initial_check_ok = revision1.was_change_detected
            if initial_check_ok:
                print("[V1 OK] Change detected in first run (as New Record).")
            else:
                print("[V1 FAIL] Initial run failed to detect change.")
                return False
                
            print()

            # --- UPDATE MOCK DATA FOR CHANGE (Simulate New Content) ---
            print("-" * 80)
            print("[UPDATE] Simulating Data Change (November 2025 Rate Increase)")
            print("-" * 80)
            
            # Update the source's scraping rules with new mock HTML
            source.scraping_rules = {"mock_html": updated_mock_html, "expected_type": "text/html"}
            db_session.add(source)
            await db_session.commit()
            print(f"[OK] Updated source {source_id} with new mock HTML.")
            print()

            # --- RUN 2: Second Scrape (With Changed Data) ---
            print("-" * 80)
            print("[RUN 2] Second Scrape - Should Detect Changes")
            print("-" * 80)
            revision2 = await run_single_scrape(db_session, source_id, scrape_num=2, timeout=60.0)
            if not revision2: return False

            # ===== VALIDATION 2: CHANGE DETECTION =====
            print("-" * 80)
            print("[VALIDATION] Change Detection Results")
            print("-" * 80)

            # 1. Did AI flag the change?
            change_flag_ok = revision2.was_change_detected
            if change_flag_ok:
                print("[V2 OK] AI Change Flag: Change correctly detected.")
            else:
                print("[V2 FAIL] AI Change Flag: Change was NOT detected!")

            # 2. Was Diff Record Created?
            diff_query = select(ChangeDiff).where(ChangeDiff.new_revision_id == revision2.id)
            diff_res = await db_session.execute(diff_query)
            diff_record = diff_res.scalars().first()
            
            diff_record_ok = bool(diff_record)
            if diff_record_ok:
                # FIX: Use correct primary key 'diff_id' instead of 'id'
                print(f"[V2 OK] ChangeDiff Record created: {diff_record.diff_id}")
            else:
                print("[V2 FAIL] ChangeDiff Record was NOT created!")

            # 3. Print Comparison Data
            print()
            print("[CHECK] FULL AI Result JSON Comparison")
            
            full_data1 = revision1.extracted_data
            full_data2 = revision2.extracted_data

            print(f"  Run 1 FULL AI RESULT (Initial):\n{json.dumps(full_data1, indent=2)}")
            print()
            print(f"  Run 2 FULL AI RESULT (Changed):\n{json.dumps(full_data2, indent=2)}")
            print()

            # 4. Final Summary
            all_ok = change_flag_ok and diff_record_ok
            test_passed = all_ok

        except Exception as e:
            print(f"[ERROR] Test failed: {e}")
            traceback.print_exc()
            test_passed = False
        finally:
            if 'source' in locals():
                if CLEANUP_ON_EXIT:
                    # FIX: Cascade delete manually because SQLite/TestDB might not support CASCADE constraints
                    print("\n[CLEANUP] Deleting test data (Child -> Parent)...")
                    
                    # 1. Delete ChangeDiffs associated with this source's revisions
                    revisions_query = select(DataRevision.id).where(DataRevision.source_id == source.id)
                    await db_session.execute(delete(ChangeDiff).where(ChangeDiff.new_revision_id.in_(revisions_query)))
                    
                    # 2. Delete DataRevisions
                    await db_session.execute(delete(DataRevision).where(DataRevision.source_id == source.id))
                    
                    # 3. Delete Source
                    await db_session.execute(delete(Source).where(Source.id == source.id))
                    await db_session.commit()
                    print(f"[CLEANUP] Source {source_id} and associated data deleted.")
                else:
                    print("\n[INFO] Cleanup Skipped. Data remains in database.")
                    print(f"[INFO] Inspect Source ID: {source.id}")
            
            print("\n" + "=" * 80)
            if test_passed:
                print("[TEST PASSED] Mock Change Detection successful!")
            else:
                print("[TEST FAILED] Mock Change Detection failed.")
            print("=" * 80)
            return test_passed


async def main():
    """Run the mock Celery worker test."""
    success = await mock_celery_scraper_worker()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())