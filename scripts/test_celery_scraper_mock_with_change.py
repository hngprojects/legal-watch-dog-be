"""
Mock Celery Worker Test: Scraper Service Pipeline with Change Detection

Simulates the actual Celery worker flow with mock data:
1. First run: Mock scrape with initial data → Extract → Store DataRevision
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

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.scraping.models.source_model import Source, SourceType, ScrapeFrequency
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization


async def mock_celery_scraper_worker_with_change():
    """
    Mock Celery worker that runs the ScraperService pipeline twice with mock data
    and validates change detection when content changes.
    """
    print("=" * 80)
    print("MOCK CELERY WORKER: Scraper Service Pipeline with Change Detection")
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
            name="UK Government Test Org",
            email="test@gov.uk",
            is_verified=True
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)
        print(f"  [OK] Organization created: {org.id}")

        project = Project(
            id=uuid4(),
            org_id=org.id,
            title="UK Minimum Wage Compliance",
            master_prompt="Extract the current National Minimum Wage and National Living Wage rates per hour. Group the rates by age category (e.g., '21 and over', '18 to 20'). Identify the 'Effective Date' for these rates.",
            description="Monitor UK minimum wage rates for compliance"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        print(f"  [OK] Project created: {project.id}")

        jurisdiction = Jurisdiction(
            id=uuid4(),
            project_id=project.id,
            name="United Kingdom",
            description="UK minimum wage regulations",
            prompt="Context: HM Revenue & Customs (HMRC) official rates for the UK."
        )
        db_session.add(jurisdiction)
        db_session.commit()
        db_session.refresh(jurisdiction)
        print(f"  [OK] Jurisdiction created: {jurisdiction.id}")

        # Mock initial data (April 2025 rates)
        initial_mock_html = """
        <html>
        <body>
        <h1>National Minimum Wage and National Living Wage rates</h1>
        <p>The national minimum wage is the minimum pay per hour almost all workers are entitled to by law.</p>
        <table>
        <tr><th>Age</th><th>Rate from April 2025</th></tr>
        <tr><td>21 and over (National Living Wage)</td><td>£12.21</td></tr>
        <tr><td>18 to 20</td><td>£10.00</td></tr>
        <tr><td>Under 18</td><td>£7.55</td></tr>
        <tr><td>Apprentice</td><td>£7.55</td></tr>
        </table>
        <p>These rates apply from April 2025.</p>
        </body>
        </html>
        """

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
        db_session.commit()
        db_session.refresh(source)
        print(f"  [OK] Source created: {source.id}")
        print()

        # ===== RUN 1: Initial Scrape =====
        print("-" * 80)
        print("[RUN 1] First Scrape - Initial Extraction (April 2025 Rates)")
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
                timeout=120.0
            )
            print(f"[OK] Scrape job completed")
            print(f"    Result: {result1}")
        except asyncio.TimeoutError:
            print(f"[ERROR] Scrape job timed out after 120 seconds")
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

        # ===== UPDATE MOCK DATA FOR CHANGE =====
        print("-" * 80)
        print("[UPDATE] Simulating Data Change (November 2025 Rate Increase)")
        print("-" * 80)
        print()

        # Updated mock data with rate changes
        updated_mock_html = """
        <html>
        <body>
        <h1>National Minimum Wage and National Living Wage rates</h1>
        <p>The national minimum wage is the minimum pay per hour almost all workers are entitled to by law.</p>
        <table>
        <tr><th>Age</th><th>Rate from November 2025</th></tr>
        <tr><td>21 and over (National Living Wage)</td><td>£12.75</td></tr>
        <tr><td>18 to 20</td><td>£10.50</td></tr>
        <tr><td>Under 18</td><td>£8.10</td></tr>
        <tr><td>Apprentice</td><td>£8.10</td></tr>
        </table>
        <p>These rates apply from November 2025.</p>
        </body>
        </html>
        """

        # Update the source's scraping rules with new mock HTML
        source.scraping_rules = {
            "mock_html": updated_mock_html,
            "expected_type": "text/html"
        }
        db_session.commit()
        print("[OK] Updated source with new mock HTML (rate increase)")
        print()

        # ===== RUN 2: Second Scrape (With Changed Data) =====
        print("-" * 80)
        print("[RUN 2] Second Scrape - Should Detect Changes (Rate Increase)")
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
                timeout=120.0
            )
            print(f"[OK] Scrape job completed")
            print(f"    Result: {result2}")
        except asyncio.TimeoutError:
            print(f"[ERROR] Scrape job timed out after 120 seconds")
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
        if revision1.id != revision2.id:
            print("[OK] Two different revisions created (content changed)")
            was_reused = False
        else:
            print("[ERROR] Same revision returned (unexpected reuse)!")
            return False

        print()

        # Check extracted data differences
        print("[CHECK] Extracted Data Changes")
        data1 = revision1.extracted_data.get("extracted_data", {})
        data2 = revision2.extracted_data.get("extracted_data", {})

        print(f"  Run 1 data (April 2025): {json.dumps(data1, indent=2)}")
        print()
        print(f"  Run 2 data (November 2025): {json.dumps(data2, indent=2)}")
        print()

        if data1 != data2:
            print("[OK] Extracted data differs (rate changes detected)")
            data_changed = True
        else:
            print("[ERROR] Extracted data identical (changes not detected)!")
            data_changed = False

        print()

        # Check confidence scores
        print("[CHECK] Confidence Scores")
        print(f"  Run 1: {revision1.ai_confidence_score}")
        print(f"  Run 2: {revision2.ai_confidence_score}")

        confidence_ok = revision1.ai_confidence_score > 0.8 and revision2.ai_confidence_score > 0.8
        if confidence_ok:
            print("[OK] High confidence scores")
        else:
            print("[WARNING] Low confidence scores")

        print()

        # Check change detection
        print("[CHECK] Change Detection")
        print(f"  Run 1 - Was Change Detected: {revision1.was_change_detected}")
        print(f"  Run 2 - Was Change Detected: {revision2.was_change_detected}")

        if revision2.was_change_detected:
            print("[OK] Change detected in second run")
            change_detection_ok = True
        else:
            print("[ERROR] No change detected despite data changes!")
            change_detection_ok = False

        print()

        # Check diff record
        print("[CHECK] Diff Record Creation")
        diff_record = db_session.query(ChangeDiff).filter(
            ChangeDiff.new_revision_id == revision2.id
        ).first()

        if diff_record:
            print(f"[OK] ChangeDiff record created: {diff_record.diff_id}")
            print(f"    Diff Summary: {diff_record.diff_patch.get('change_summary', 'N/A')}")
            print(f"    Risk Level: {diff_record.diff_patch.get('risk_level', 'N/A')}")
            diff_ok = True
        else:
            print("[ERROR] No ChangeDiff record created!")
            diff_ok = False

        print()

        # ===== SUMMARY =====
        print("=" * 80)
        print("[SUMMARY]")
        print("=" * 80)
        print()

        all_ok = data_changed and confidence_ok and change_detection_ok and diff_ok

        print(f"Data Changes Detected: {'[OK]' if data_changed else '[FAIL]'}")
        print(f"Confidence Scores: {'[OK]' if confidence_ok else '[FAIL]'}")
        print(f"Change Detection: {'[OK]' if change_detection_ok else '[FAIL]'}")
        print(f"Diff Record Creation: {'[OK]' if diff_ok else '[FAIL]'}")
        print()

        if all_ok:
            print("[SUCCESS] All validations passed!")
            print("The mock Celery worker pipeline correctly detected changes.")
            print("Rate increases were identified and diff records created.")
            return True
        else:
            print("[FAILURE] Some validations failed.")
            return False

    except Exception as e:
        print(f"[ERROR] Exception during test: {e}")
        traceback.print_exc()
        return False
    finally:
        db_session.close()


async def main():
    """Run the mock Celery worker test with change detection."""
    success = await mock_celery_scraper_worker_with_change()

    print()
    print("=" * 80)
    if success:
        print("[TEST PASSED] Mock Celery worker pipeline with change detection successful!")
        print("=" * 80)
        return 0
    else:
        print("[TEST FAILED] Mock Celery worker pipeline with change detection failed.")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)