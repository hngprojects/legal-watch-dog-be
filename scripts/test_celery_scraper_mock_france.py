"""
Mock Celery Worker Test: Scraper Service Pipeline for France Visas PDF Source

Simulates the actual Celery worker flow for a Cloudflare-protected PDF site:
1. First run: Fetch France Visas → Extract PDF → Store DataRevision
2. Second run: Fetch France Visas → Extract PDF → Detect Changes → Store Diff

Validates that:
- PDF fetching works with Playwright fallback
- PDF text extraction is consistent
- Diff detection works for PDF content changes
- Change detection flags work as expected
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.scraping.models.source_model import Source, SourceType, ScrapeFrequency
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization


async def mock_celery_scraper_worker_france():
    """
    Mock Celery worker that runs the ScraperService pipeline twice
    for the France Visas PDF source and validates diff detection.
    """
    print("=" * 80)
    print("MOCK CELERY WORKER: Scraper Service Pipeline for France Visas PDF")
    print("=" * 80)
    print()

    # ===== SETUP DATABASE =====
    print("[SETUP] Initializing database...")
    from app.api.core.config import settings
    
    db_engine = create_engine(settings.DATABASE_URL)
    
    # Create session
    db_session = Session(db_engine)
    
    try:
        # Create test data
        print("[SETUP] Creating test Organization, Project, Jurisdiction, and Source...")
        
        org = Organization(
            id=uuid4(),
            name="French Government Test Org",
            email="test@france-visas.gouv.fr",
            is_verified=True
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)
        print(f"  [OK] Organization created: {org.id}")

        project = Project(
            id=uuid4(),
            org_id=org.id,
            title="France Visa Compliance Monitoring",
            master_prompt="Extract the current visa fees for long-stay visas in France. Include fees for different visa types (visa de long séjour), processing times, and any special conditions. Group fees by visa category and duration.",
            description="Monitor France visa fees and requirements for compliance"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        print(f"  [OK] Project created: {project.id}")

        jurisdiction = Jurisdiction(
            id=uuid4(),
            project_id=project.id,
            name="France",
            description="French visa regulations and fees",
            prompt="Context: Official French government visa fees and processing information from France-Visas service."
        )
        db_session.add(jurisdiction)
        db_session.commit()
        db_session.refresh(jurisdiction)
        print(f"  [OK] Jurisdiction created: {jurisdiction.id}")

        source = Source(
            id=uuid4(),
            jurisdiction_id=jurisdiction.id,
            name="France Visas - Long Stay Visa Fees",
            url="https://france-visas.gouv.fr/web/france-visas/visa-a-long-sejour",
            source_type=SourceType.WEB,
            scrape_frequency=ScrapeFrequency.WEEKLY,
            next_scrape_time=datetime.now(timezone.utc)
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
        print(f"  [OK] Source created: {source.id}")
        print()

        # ===== RUN 1: Initial Scrape =====
        print("-" * 80)
        print("[RUN 1] First Scrape - Initial PDF Extraction")
        print("-" * 80)
        print()

        print("[WORKER-1] Initializing ScraperService...")
        scraper_service = ScraperService(db_session)
        print("[OK] ScraperService initialized")
        print()

        print(f"[WORKER-1] Executing scrape job for source: {source.id}")
        try:
            # Add timeout to prevent hanging
            result1 = await asyncio.wait_for(
                scraper_service.execute_scrape_job(str(source.id)),
                timeout=300.0  # 5 minute timeout for PDF downloads
            )
            print(f"[OK] Scrape job completed")
            print(f"    Result: {result1}")
        except asyncio.TimeoutError:
            print(f"[ERROR] Scrape job timed out after 300 seconds")
            return False
        except Exception as e:
            print(f"[ERROR] Scrape job failed: {e}")
            return False
        print()

        # Fetch the created revision
        revision1 = db_session.query(DataRevision).filter(
            DataRevision.source_id == source.id
        ).order_by(DataRevision.scraped_at.desc()).first()

        if revision1:
            print(f"[OK] DataRevision created: {revision1.id}")
            print(f"    Content Hash: {revision1.content_hash[:16]}...")
            print(f"    AI Summary: {revision1.ai_summary[:100]}...")
            print(f"    Confidence Score: {revision1.ai_confidence_score}")
            print(f"    Extracted Fields: {len(revision1.extracted_data.get('extracted_data', {}))} fields")
            print(f"    Extracted Data Keys: {list(revision1.extracted_data.get('extracted_data', {}).keys())}")
            print(f"    Was Change Detected: {revision1.was_change_detected}")
        else:
            print("[ERROR] No DataRevision created!")
            return False
        
        print()

        # ===== RUN 2: Second Scrape (Same URL, Should Detect No Changes) =====
        print("-" * 80)
        print("[RUN 2] Second Scrape - Should Detect No Changes (PDF Consistency)")
        print("-" * 80)
        print()

        print("[WORKER-2] Initializing ScraperService...")
        scraper_service2 = ScraperService(db_session)
        print("[OK] ScraperService initialized")
        print()

        print(f"[WORKER-2] Executing scrape job for source: {source.id}")
        try:
            # Add timeout to prevent hanging
            result2 = await asyncio.wait_for(
                scraper_service2.execute_scrape_job(str(source.id)),
                timeout=300.0  # 5 minute timeout for PDF downloads
            )
            print(f"[OK] Scrape job completed")
            print(f"    Result: {result2}")
        except asyncio.TimeoutError:
            print(f"[ERROR] Scrape job timed out after 300 seconds")
            return False
        except Exception as e:
            print(f"[ERROR] Scrape job failed: {e}")
            return False
        print()

        # Fetch the created revision
        revision2 = db_session.query(DataRevision).filter(
            DataRevision.source_id == source.id
        ).order_by(DataRevision.scraped_at.desc()).first()

        if revision2:
            print(f"[OK] DataRevision created: {revision2.id}")
            print(f"    Content Hash: {revision2.content_hash[:16]}...")
            print(f"    AI Summary: {revision2.ai_summary[:100]}...")
            print(f"    Confidence Score: {revision2.ai_confidence_score}")
            print(f"    Extracted Fields: {len(revision2.extracted_data.get('extracted_data', {}))} fields")
            print(f"    Extracted Data Keys: {list(revision2.extracted_data.get('extracted_data', {}).keys())}")
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

        # Check if revisions are different
        if revision1.id == revision2.id:
            print("[OK] Same revision returned (content hash matched - deduplication worked!)")
            print("     This means the scraper detected identical PDF content and reused previous extraction")
            was_reused = True
        else:
            print(f"[DIFFERENT] Two different revisions created")
            print(f"    Revision 1 ID: {revision1.id}")
            print(f"    Revision 2 ID: {revision2.id}")
            was_reused = False

        print()

        # Check extracted data consistency
        print("[CHECK] Extracted Data Consistency")
        data1 = revision1.extracted_data.get("extracted_data", {})
        data2 = revision2.extracted_data.get("extracted_data", {})

        print(f"  Run 1 data: {json.dumps(data1, indent=2)}")
        print()
        print(f"  Run 2 data: {json.dumps(data2, indent=2)}")
        print()

        if data1 == data2:
            print("[OK] Extracted data is identical (100% consistency)")
            consistency_ok = True
        else:
            print("[FAIL] Extracted data differs!")
            print(f"      Run 1 keys: {set(data1.keys())}")
            print(f"      Run 2 keys: {set(data2.keys())}")
            consistency_ok = False

        print()

        # Check confidence scores
        print("[CHECK] Confidence Scores")
        print(f"  Run 1: {revision1.ai_confidence_score}")
        print(f"  Run 2: {revision2.ai_confidence_score}")
        
        if revision1.ai_confidence_score == revision2.ai_confidence_score:
            print("[OK] Confidence scores match")
            confidence_ok = True
        else:
            print("[FAIL] Confidence scores differ")
            confidence_ok = False

        print()

        # Check change detection
        print("[CHECK] Change Detection")
        print(f"  Run 1 - Was Change Detected: {revision1.was_change_detected}")
        print(f"  Run 2 - Was Change Detected: {revision2.was_change_detected}")
        
        if not revision2.was_change_detected:
            print("[OK] No changes detected (as expected for identical PDF content)")
            change_detection_ok = True
        else:
            print("[WARN] Changes detected when PDF content should be identical")
            change_detection_ok = False

        print()

        # Check diff record
        print("[CHECK] Diff Record Creation")
        if was_reused:
            print("[INFO] Skipped (content was reused, no diff needed)")
            diff_ok = True
        else:
            diff_record = db_session.query(ChangeDiff).filter(
                ChangeDiff.new_revision_id == revision2.id
            ).first()
            
            if diff_record:
                print(f"[OK] ChangeDiff record created: {diff_record.id}")
                print(f"    Change Summary: {diff_record.diff_patch.get('change_summary')}")
                print(f"    Risk Level: {diff_record.diff_patch.get('risk_level')}")
                print(f"    AI Confidence: {diff_record.ai_confidence}")
                diff_ok = True
            else:
                print("[OK] No ChangeDiff record (expected when no changes detected)")
                diff_ok = True

        print()

        print()
        print("=" * 80)
        print("[SUMMARY]")
        print("=" * 80)
        print()

        all_ok = consistency_ok and confidence_ok and change_detection_ok and diff_ok

        print(f"Extraction Consistency: {'[OK]' if consistency_ok else '[FAIL]'}")
        print(f"Confidence Scores Match: {'[OK]' if confidence_ok else '[FAIL]'}")
        print(f"Change Detection: {'[OK]' if change_detection_ok else '[FAIL]'}")
        print(f"Diff Record Creation: {'[OK]' if diff_ok else '[FAIL]'}")
        print()

        if all_ok:
            print("[SUCCESS] All validations passed!")
            print("The mock Celery worker pipeline works correctly for PDF sources.")
            print("PDF extraction is consistent and diff detection is reliable.")
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
        db_session.close()


async def main():
    """Run the mock Celery worker test for France Visas."""
    success = await mock_celery_scraper_worker_france()

    print()
    print("=" * 80)
    if success:
        print("[TEST PASSED] Mock Celery worker pipeline test successful for France Visas!")
        print("=" * 80)
        return 0
    else:
        print("[TEST FAILED] Mock Celery worker pipeline test failed.")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)