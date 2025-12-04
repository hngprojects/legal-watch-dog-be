"""
Full Integration Test with Mock HTTP Server

Simulates a webpage that changes between scrapes to ensure
change detection actually works.
"""

import asyncio
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from app.api.core.config import settings
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
)
from app.api.modules.v1.notifications.service.revision_notification_task import (
    send_revision_notifications,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import (
    ScrapeFrequency,
    Source,
    SourceType,
)
from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.users.models.users_model import User

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Global state for mock server
PAGE_VERSION = 1


class MockWagePageHandler(BaseHTTPRequestHandler):
    """Mock HTTP handler that serves different wage data based on version."""

    def do_GET(self):
        """Handle GET requests."""
        global PAGE_VERSION

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if PAGE_VERSION == 1:
            # Initial version - Original rates
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>National Minimum Wage Rates - Mock Page</title>
            </head>
            <body>
                <h1>National Minimum Wage and Living Wage Rates</h1>
                <h2>Current Rates (Effective April 2024)</h2>
                
                <div class="rate-section">
                    <h3>Age 21 and over (National Living Wage)</h3>
                    <p class="rate">£11.44 per hour</p>
                </div>
                
                <div class="rate-section">
                    <h3>Age 18 to 20</h3>
                    <p class="rate">£8.60 per hour</p>
                </div>
                
                <div class="rate-section">
                    <h3>Under 18</h3>
                    <p class="rate">£6.40 per hour</p>
                </div>
                
                <div class="rate-section">
                    <h3>Apprentice</h3>
                    <p class="rate">£6.40 per hour</p>
                </div>
                
                <p class="effective-date">Effective Date: 1 April 2024</p>
            </body>
            </html>
            """
        else:
            # Updated version - New rates (CHANGED!)
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>National Minimum Wage Rates - Mock Page</title>
            </head>
            <body>
                <h1>National Minimum Wage and Living Wage Rates</h1>
                <h2>Current Rates (Effective April 2025)</h2>
                
                <div class="rate-section">
                    <h3>Age 21 and over (National Living Wage)</h3>
                    <p class="rate">£12.21 per hour</p>
                </div>
                
                <div class="rate-section">
                    <h3>Age 18 to 20</h3>
                    <p class="rate">£10.00 per hour</p>
                </div>
                
                <div class="rate-section">
                    <h3>Under 18</h3>
                    <p class="rate">£7.55 per hour</p>
                </div>
                
                <div class="rate-section">
                    <h3>Apprentice</h3>
                    <p class="rate">£7.55 per hour</p>
                </div>
                
                <p class="effective-date">Effective Date: 1 April 2025</p>
            </body>
            </html>
            """

        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_mock_server(port=8888):
    """Start mock HTTP server in background thread."""
    server = HTTPServer(("localhost", port), MockWagePageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[MOCK SERVER] Started on http://localhost:{port}")
    return server


async def run_full_integration_test():
    """
    Full integration test with mock server that changes between scrapes.
    """
    global PAGE_VERSION

    print("=" * 80)
    print("INTEGRATION TEST: User to Notification with Mock Changing Webpage")
    print("=" * 80)
    print()

    # Start mock HTTP server
    mock_port = 8888
    mock_server = start_mock_server(mock_port)
    mock_url = f"http://localhost:{mock_port}"

    try:
        print("[SETUP] Initializing Async Database Session...")
        db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(db_url, echo=False)
        async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session_factory() as db_session:
            try:
                # ================================================================
                # STEP 1-6: Create User, Org, Project, Jurisdiction, Source
                # ================================================================
                print("-" * 80)
                print("[STEPS 1-6] Creating Test Entities")
                print("-" * 80)

                user = User(
                    id=uuid4(),
                    email="test.user3@example.com",
                    name="Test User",
                    hashed_password="hashed_password_placeholder",
                    auth_provider="local",
                    is_active=True,
                    is_verified=True,
                )
                db_session.add(user)
                await db_session.commit()
                await db_session.refresh(user)
                print(f"  [OK] User: {user.email}")

                organization = Organization(
                    id=uuid4(),
                    name="Test Compliance Org 3",
                    email="admin@testorg2.com",
                    is_verified=True,
                )
                db_session.add(organization)
                await db_session.commit()
                await db_session.refresh(organization)
                print(f"  [OK] Organization: {organization.name}")

                project = Project(
                    id=uuid4(),
                    org_id=organization.id,
                    title="Wage Monitor Test",
                    master_prompt=(
                        "Extract minimum wage rates by age category and effective date."
                    ),
                    description="Test project for wage monitoring",
                )
                db_session.add(project)
                await db_session.commit()
                await db_session.refresh(project)
                print(f"  [OK] Project: {project.title}")

                project_user = ProjectUser(
                    id=uuid4(),
                    project_id=project.id,
                    user_id=user.id,
                )
                db_session.add(project_user)
                await db_session.commit()
                print("  [OK] User linked to project")

                jurisdiction = Jurisdiction(
                    id=uuid4(),
                    project_id=project.id,
                    name="UK Mock Test",
                    description="Mock UK jurisdiction for testing",
                    prompt="Extract wage rates and effective dates",
                )
                db_session.add(jurisdiction)
                await db_session.commit()
                await db_session.refresh(jurisdiction)
                print(f"  [OK] Jurisdiction: {jurisdiction.name}")

                source = Source(
                    id=uuid4(),
                    jurisdiction_id=jurisdiction.id,
                    name="Mock Minimum Wage Page",
                    url=mock_url,
                    source_type=SourceType.WEB,
                    scrape_frequency=ScrapeFrequency.WEEKLY,
                    next_scrape_time=datetime.now(timezone.utc),
                )
                db_session.add(source)
                await db_session.commit()
                await db_session.refresh(source)
                print(f"  [OK] Source: {source.url}")
                print()

                # ================================================================
                # STEP 7: First Scrape (Version 1 - Original Rates)
                # ================================================================
                print("=" * 80)
                print("[STEP 7] First Scrape - Original Rates (Version 1)")
                print("=" * 80)
                print(f"Mock Server Version: {PAGE_VERSION}")
                print()

                scraper_service = ScraperService(db_session)
                print(f"[SCRAPER-1] Scraping: {mock_url}")

                try:
                    result1 = await asyncio.wait_for(
                        scraper_service.execute_scrape_job(str(source.id)),
                        timeout=180.0,
                    )
                    print("[OK] First scrape completed")
                    print(f"    Result: {result1}")
                except asyncio.TimeoutError:
                    print("[ERROR] First scrape timed out")
                    return False
                print()

                query_rev = (
                    select(DataRevision)
                    .where(DataRevision.source_id == source.id)
                    .order_by(DataRevision.scraped_at.desc())
                )
                result_rev1 = await db_session.execute(query_rev)
                revision1 = result_rev1.scalars().first()

                if revision1:
                    print(f"[OK] Revision 1: {revision1.id}")
                    print(f"    Content Hash: {revision1.content_hash}")
                    print(f"    AI Summary: {(revision1.ai_summary or '')[:150]}...")
                    print(f"    Is Baseline: {revision1.is_baseline}")
                    print(f"    Change Detected: {revision1.was_change_detected}")

                    # Show extracted data
                    extracted = revision1.extracted_data.get("extracted_data", {}).get(
                        "key_value_pairs", {}
                    )
                    print(f"    Extracted Fields: {list(extracted.keys())}")
                else:
                    print("[ERROR] No revision created!")
                    return False
                print()

                # ================================================================
                # STEP 8: Update Mock Server to Version 2
                # ================================================================
                print("=" * 80)
                print("[STEP 8] Updating Mock Server Content")
                print("=" * 80)
                PAGE_VERSION = 2
                print(f"Mock Server Version: {PAGE_VERSION} (RATES CHANGED!)")
                print("  - Age 21+: £11.44 → £12.21")
                print("  - Age 18-20: £8.60 → £10.00")
                print("  - Under 18: £6.40 → £7.55")
                print("  - Effective Date: April 2024 → April 2025")
                print()

                # ================================================================
                # STEP 9: Second Scrape (Version 2 - Updated Rates)
                # ================================================================
                print("=" * 80)
                print("[STEP 9] Second Scrape - Updated Rates (Version 2)")
                print("=" * 80)

                scraper_service2 = ScraperService(db_session)
                print(f"[SCRAPER-2] Scraping: {mock_url}")

                try:
                    result2 = await asyncio.wait_for(
                        scraper_service2.execute_scrape_job(str(source.id)),
                        timeout=180.0,
                    )
                    print("[OK] Second scrape completed")
                    print(f"    Result: {result2}")
                except asyncio.TimeoutError:
                    print("[ERROR] Second scrape timed out")
                    return False
                print()

                result_rev2 = await db_session.execute(query_rev)
                revision2 = result_rev2.scalars().first()

                if revision2:
                    print(f"[OK] Revision 2: {revision2.id}")
                    print(f"    Content Hash: {revision2.content_hash}")
                    print(f"    Change Detected: {revision2.was_change_detected}")
                    print(f"    Same as Rev1: {revision1.id == revision2.id}")

                    extracted2 = revision2.extracted_data.get("extracted_data", {}).get(
                        "key_value_pairs", {}
                    )
                    print(f"    Extracted Fields: {list(extracted2.keys())}")
                else:
                    print("[ERROR] No second revision!")
                    return False
                print()

                # ================================================================
                # STEP 10: Trigger Notifications
                # ================================================================
                print("=" * 80)
                print("[STEP 10] Triggering Notification System")
                print("=" * 80)

                # Use revision2 which should have changes
                notification_revision_id = revision2.id

                print(f"[NOTIFICATION] Sending for revision: {notification_revision_id}")
                print(f"               Change detected: {revision2.was_change_detected}")

                try:
                    await send_revision_notifications(str(notification_revision_id))
                    print("[OK] Notification task completed")
                except Exception as e:
                    print(f"[ERROR] Notification failed: {e}")
                    import traceback

                    traceback.print_exc()
                    return False
                print()

                # ================================================================
                # STEP 11: Verify Notifications
                # ================================================================
                print("=" * 80)
                print("[STEP 11] Verifying Notifications")
                print("=" * 80)

                query_notif = select(Notification).where(
                    Notification.revision_id == notification_revision_id
                )
                result_notif = await db_session.execute(query_notif)
                notifications = result_notif.scalars().all()

                if len(notifications) > 0:
                    print(f"[OK] {len(notifications)} notification(s) created")
                    for notif in notifications:
                        print(f"\n  Notification: {notif.notification_id}")
                        print(f"  User: {notif.user_id}")
                        print(f"  Type: {notif.notification_type}")
                        print(f"  Title: {notif.title}")
                        print(f"  Status: {notif.status}")
                        print(f"  Message: {notif.message[:100]}...")

                        if notif.status == NotificationStatus.SENT:
                            print("  ✓ Email SENT")
                        elif notif.status == NotificationStatus.FAILED:
                            print("  ✗ Email FAILED")
                        else:
                            print("  ⧗ Email PENDING")
                else:
                    print("[ERROR] No notifications created!")
                    return False
                print()

                # ================================================================
                # STEP 12: Test Idempotency
                # ================================================================
                print("=" * 80)
                print("[STEP 12] Testing Idempotency")
                print("=" * 80)

                print("[NOTIFICATION] Re-running notification task...")
                try:
                    await send_revision_notifications(str(notification_revision_id))
                    print("[OK] Second notification completed")
                except Exception as e:
                    print(f"[ERROR] Second notification failed: {e}")
                    return False
                print()

                result_notif2 = await db_session.execute(query_notif)
                notifications_after = result_notif2.scalars().all()

                if len(notifications_after) == len(notifications):
                    print("[OK] Idempotency verified")
                    print(f"    Count: {len(notifications_after)}")
                else:
                    print(
                        f"[WARN] Count changed: {len(notifications)} → {len(notifications_after)}"
                    )
                print()

                # ================================================================
                # VALIDATION SUMMARY
                # ================================================================
                print("=" * 80)
                print("[VALIDATION SUMMARY]")
                print("=" * 80)

                # Check if content actually changed
                content_changed = revision1.content_hash != revision2.content_hash
                change_detected = revision2.was_change_detected
                emails_sent = any(n.status == NotificationStatus.SENT for n in notifications)

                checks = {
                    "User Created": user.id is not None,
                    "Organization Created": organization.id is not None,
                    "Project Created": project.id is not None,
                    "User Linked": project_user.user_id is not None,
                    "Jurisdiction Created": jurisdiction.id is not None,
                    "Source Created": source.id is not None,
                    "First Scrape Success": revision1 is not None,
                    "Second Scrape Success": revision2 is not None,
                    "Content Actually Changed": content_changed,
                    "Change Detected by System": change_detected,
                    "Notifications Created": len(notifications) > 0,
                    "Emails Sent": emails_sent,
                    "Idempotency Passed": len(notifications_after) == len(notifications),
                }

                all_passed = True
                for check_name, passed in checks.items():
                    status = "[OK]" if passed else "[FAIL]"
                    print(f"{status} {check_name}")
                    if not passed:
                        all_passed = False

                # Extra info
                print()
                print("Additional Details:")
                print(f"  Revision 1 Hash: {revision1.content_hash}")
                print(f"  Revision 2 Hash: {revision2.content_hash}")
                print(f"  Hashes Different: {content_changed}")
                print(f"  Notifications Sent: {len(notifications)}")

                print()
                print("=" * 80)
                print(f"[RESULT] Test {'PASSED' if all_passed else 'FAILED'}")
                print("=" * 80)
                print()

                return all_passed

            except Exception as e:
                print(f"[ERROR] Exception: {e}")
                import traceback

                traceback.print_exc()
                return False

    finally:
        # Shutdown mock server
        print("[CLEANUP] Shutting down mock server...")
        mock_server.shutdown()
        PAGE_VERSION = 1  # Reset for next run


async def main():
    """Run the integration test."""
    success = await run_full_integration_test()
    print()
    print("=" * 80)
    print(f"Integration Test: {'SUCCESS' if success else 'FAILURE'}")
    print("=" * 80)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
