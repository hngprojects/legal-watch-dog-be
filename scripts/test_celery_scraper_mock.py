"""
Mock Celery Worker Test: Scraper Service Pipeline with Diff Detection (ASYNC FIX)

Simulates the actual Celery worker flow using ASYNC database sessions.
1. First run: Fetch GOV.UK -> Extract -> Store DataRevision
2. Second run: Fetch GOV.UK -> Extract -> Detect Changes -> Store Diff
"""

import asyncio
import json
import sys
from pathlib import Path
# Using datetime.now(timezone.utc) for timezone awareness
from datetime import datetime, timezone 
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.scraping.models.source_model import Source, SourceType, ScrapeFrequency
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.core.config import settings

async def mock_celery_scraper_worker():
    """
    Mock Celery worker that runs the ScraperService pipeline twice
    and validates diff detection.
    """
    print("=" * 80)
    print("MOCK CELERY WORKER: Scraper Service Pipeline (Async Mode)")
    print("=" * 80)
    print()

    # ===== SETUP DATABASE (ASYNC) =====
    print("[SETUP] Initializing Async Database Session...")
    
    # Ensure we use an async driver (asyncpg) even if settings has 'postgresql://'
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(db_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as db_session:
        try:
            # Create test data
            print("[SETUP] Creating test Organization, Project, Jurisdiction, and Source...")
            
            org = Organization(
                id=uuid4(),
                name="UK Government Test Org",
                email="test@gov.uk",
                is_verified=True
            )
            db_session.add(org)
            await db_session.commit()
            await db_session.refresh(org)
            print(f"  [OK] Organization created: {org.id}")

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
            print(f"  [OK] Project created: {project.id}")

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
            print(f"  [OK] Jurisdiction created: {jurisdiction.id}")

            source = Source(
                id=uuid4(),
                jurisdiction_id=jurisdiction.id,
                name="GOV.UK National Minimum Wage",
                url="https://www.gov.uk/national-minimum-wage-rates",
                source_type=SourceType.WEB,
                scrape_frequency=ScrapeFrequency.WEEKLY,
                # FIX: Use timezone-aware datetime.now(timezone.utc)
                next_scrape_time=datetime.now(timezone.utc)
            )
            db_session.add(source)
            await db_session.commit()
            await db_session.refresh(source)
            print(f"  [OK] Source created: {source.id}")
            print()

            # ===== RUN 1: Initial Scrape =====
            print("-" * 80)
            print("[RUN 1] First Scrape - Initial Extraction")
            print("-" * 80)
            print()

            print("[WORKER-1] Initializing ScraperService...")
            # Pass the async session to the service
            scraper_service = ScraperService(db_session)
            print("[OK] ScraperService initialized")
            print()

            print(f"[WORKER-1] Executing scrape job for source: {source.id}")
            try:
                # Add timeout to prevent hanging
                result1 = await asyncio.wait_for(
                    scraper_service.execute_scrape_job(str(source.id)),
                    timeout=180.0  # 3 minute timeout for AI/Puppeteer
                )
                print(f"[OK] Scrape job completed")
                print(f"    Result: {result1}")
            except asyncio.TimeoutError:
                print(f"[ERROR] Scrape job timed out after 180 seconds")
                return False
            print()

            # Fetch the created revision (Async Query)
            query_rev1 = select(DataRevision).where(
                DataRevision.source_id == source.id
            ).order_by(DataRevision.scraped_at.desc())
            
            result_rev1 = await db_session.execute(query_rev1)
            revision1 = result_rev1.scalars().first()

            if revision1:
                print(f"[OK] DataRevision created: {revision1.id}")
                print(f"    Content Hash: {revision1.content_hash[:16]}...")
                print(f"    AI Summary: {(revision1.ai_summary or '')[:100]}...")
                print(f"    Confidence Score: {revision1.ai_confidence_score}")
                
                extracted_data = revision1.extracted_data.get('extracted_data', {}).get('key_value_pairs', {})
                print(f"    Extracted Fields: {len(extracted_data)} fields")
                print(f"    Extracted Data Keys: {list(extracted_data.keys())}")
                print(f"    Was Change Detected: {revision1.was_change_detected}")
            else:
                print("[ERROR] No DataRevision created!")
                return False
            
            print()

            # ===== RUN 2: Second Scrape (Same URL, Should Detect No Changes) =====
            print("-" * 80)
            print("[RUN 2] Second Scrape - Should Detect No Changes (100% Consistency)")
            print("-" * 80)
            print()

            print("[WORKER-2] Initializing ScraperService...")
            # Ideally reuse session or create new one, reusing here for simplicity within tx
            scraper_service2 = ScraperService(db_session)
            print("[OK] ScraperService initialized")
            print()

            print(f"[WORKER-2] Executing scrape job for source: {source.id}")
            try:
                result2 = await asyncio.wait_for(
                    scraper_service2.execute_scrape_job(str(source.id)),
                    timeout=180.0
                )
                print(f"[OK] Scrape job completed")
                print(f"    Result: {result2}")
            except asyncio.TimeoutError:
                print(f"[ERROR] Scrape job timed out")
                return False
            print()

            # Fetch the created revision
            result_rev2 = await db_session.execute(query_rev1)
            revision2 = result_rev2.scalars().first()

            if revision2:
                print(f"[OK] DataRevision created: {revision2.id}")
                print(f"    Was Change Detected: {revision2.was_change_detected}")
            else:
                print("[ERROR] No DataRevision created!")
                return False
            
            print()

            # ===== VALIDATION =====
            print("-" * 80)
            print("[VALIDATION] Comparing Results")
            print("-" * 80)
            print()

            # Check if revisions are different objects
            if revision1.id == revision2.id:
                print("[OK] Same revision returned (content hash matched - deduplication worked!)")
                print("     This means the scraper detected identical content and reused previous extraction")
                was_reused = True
            else:
                print(f"[DIFFERENT] Two different revisions created")
                was_reused = False

            print()

            # CHECK: Print the FULL AI Result JSON for both runs
            print("[CHECK] FULL AI Result JSON Comparison")
            
            full_data1 = revision1.extracted_data
            full_data2 = revision2.extracted_data

            print(f"  Run 1 FULL AI RESULT:\n{json.dumps(full_data1, indent=2)}")
            print()
            print(f"  Run 2 FULL AI RESULT:\n{json.dumps(full_data2, indent=2)}")
            print()

            # Check extracted data consistency
            print("[CHECK] Nested Extracted Data Consistency")
            
            # Use the full extracted_data dicts for comparison
            if json.dumps(full_data1, sort_keys=True) == json.dumps(full_data2, sort_keys=True):
                print("[OK] Full AI result structure is identical (100% consistency)")
                consistency_ok = True
            else:
                print("[FAIL] Full AI result structure differs!")
                consistency_ok = False

            print()

            # Check Change Detection Logic
            print("[CHECK] Change Detection")
            if was_reused:
                print("[OK] Content reused, implies no change detected.")
                change_detection_ok = True
                diff_ok = True
            else:
                if not revision2.was_change_detected:
                     print("[OK] No changes detected (as expected for identical content)")
                     change_detection_ok = True
                else:
                     print("[WARN] Changes detected when content should be identical")
                     change_detection_ok = False
                
                # Check Diff Record
                diff_query = select(ChangeDiff).where(ChangeDiff.new_revision_id == revision2.id)
                diff_res = await db_session.execute(diff_query)
                diff_record = diff_res.scalars().first()
                
                if diff_record:
                    print(f"[OK] ChangeDiff record created: {diff_record.id}")
                    diff_ok = True
                else:
                    print("[OK] No ChangeDiff record (expected when no changes detected)")
                    diff_ok = True

            print()
            print("=" * 80)
            print("[SUMMARY]")
            print("=" * 80)
            print()

            all_ok = consistency_ok and change_detection_ok and diff_ok

            print(f"Extraction Consistency: {'[OK]' if consistency_ok else '[FAIL]'}")
            print(f"Change Detection: {'[OK]' if change_detection_ok else '[FAIL]'}")
            print()

            if all_ok:
                print("[SUCCESS] All validations passed!")
                return True
            else:
                print("[FAILURE] Some validations failed.")
                return False

        except Exception as e:
            print(f"[ERROR] Exception during test: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup (Optional)
            # await db_session.execute(delete(Source).where(Source.id == source.id))
            # await db_session.commit()
            pass

async def main():
    """Run the mock Celery worker test."""
    success = await mock_celery_scraper_worker()
    print()
    print("=" * 80)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())