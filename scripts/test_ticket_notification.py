"""
Script to test the ticket notification endpoint.

This script:
1. Creates minimal test data (user, org, project, ticket) in the database
2. Calls the notification endpoint directly
3. Cleans up after itself

Usage:
    uv run python scripts/test_ticket_notification.py
"""

import asyncio
import uuid

import httpx
from sqlalchemy.future import select

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.tickets.models.ticket_model import Ticket
from app.api.modules.v1.users.models.users_model import User


async def create_test_data(session):
    """Create minimal test data and return the ticket ID."""
    # Create test user
    test_user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        name="Test User",
        hashed_password="test_hashed_password",
        is_active=True,
        is_verified=True,
    )
    session.add(test_user)
    await session.flush()

    # Create test organization
    test_org = Organization(
        id=uuid.uuid4(),
        name=f"Test Org {uuid.uuid4().hex[:8]}",
        industry="Legal",
    )
    session.add(test_org)
    await session.flush()

    # Create test project
    test_project = Project(
        id=uuid.uuid4(),
        org_id=test_org.id,
        title="Test Project",
    )
    session.add(test_project)
    await session.flush()

    # Create test ticket
    test_ticket = Ticket(
        id=uuid.uuid4(),
        title="Test Ticket for Notification",
        description="This is a test ticket to verify notifications work.",
        organization_id=test_org.id,
        project_id=test_project.id,
        created_by_user_id=test_user.id,
        is_manual=True,
    )
    session.add(test_ticket)
    await session.commit()

    return {
        "ticket_id": str(test_ticket.id),
        "user_id": str(test_user.id),
        "org_id": str(test_org.id),
        "project_id": str(test_project.id),
    }


async def cleanup_test_data(session, ids: dict):
    """Clean up the test data created."""
    # Delete in reverse order of creation to respect FK constraints
    ticket_result = await session.execute(
        select(Ticket).where(Ticket.id == uuid.UUID(ids["ticket_id"]))
    )
    ticket = ticket_result.scalar_one_or_none()
    if ticket:
        await session.delete(ticket)

    project_result = await session.execute(
        select(Project).where(Project.id == uuid.UUID(ids["project_id"]))
    )
    project = project_result.scalar_one_or_none()
    if project:
        await session.delete(project)

    org_result = await session.execute(
        select(Organization).where(Organization.id == uuid.UUID(ids["org_id"]))
    )
    org = org_result.scalar_one_or_none()
    if org:
        await session.delete(org)

    user_result = await session.execute(select(User).where(User.id == uuid.UUID(ids["user_id"])))
    user = user_result.scalar_one_or_none()
    if user:
        await session.delete(user)

    await session.commit()


async def call_notification_endpoint(ticket_id: str, message: str):
    """Call the ticket notification endpoint."""
    url = f"http://localhost:8000/api/v1/notifications/tickets/{ticket_id}/send"
    params = {"message": message}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params)
        return response


async def main():
    print("=" * 60)
    print("TICKET NOTIFICATION ENDPOINT TEST")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        print("\n1. Creating test data...")
        ids = await create_test_data(session)
        print(f"   Created ticket: {ids['ticket_id']}")
        print(f"   Created user:   {ids['user_id']}")
        print(f"   Created org:    {ids['org_id']}")
        print(f"   Created project:{ids['project_id']}")

        print("\n2. Calling notification endpoint...")
        test_message = "Test notification from dummy script"
        response = await call_notification_endpoint(ids["ticket_id"], test_message)

        print(f"   Status Code: {response.status_code}")
        print(f"   Response:    {response.json()}")

        if response.status_code == 200:
            print("\n   ✅ SUCCESS: Endpoint responded correctly!")
        else:
            print(f"\n   ❌ FAILED: Unexpected status code {response.status_code}")

        print("\n3. Cleaning up test data...")
        await cleanup_test_data(session, ids)
        print("   Cleanup complete.")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

    # Also print curl command for manual testing
    print("\n📋 CURL COMMAND FOR MANUAL TESTING (Swagger/Postman):")
    print("-" * 60)
    print(
        'curl -X POST "http://localhost:8000/api/v1/notifications/tickets/<TICKET_ID>/send?message=Test%20notification"'
    )
    print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
