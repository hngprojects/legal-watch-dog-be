"""
Test script for ticket invitation system - Using bcrypt directly

This version uses bcrypt directly instead of passlib to avoid compatibility issues.

Prerequisites:
- Database must be running
- Run alembic migrations first: `alembic upgrade head`
"""

import asyncio
import uuid
from datetime import datetime, timezone

import bcrypt
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketPriority, TicketStatus
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User

# API Base URL (change this to match your running server)
API_BASE_URL = "http://localhost:8001/api/v1"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def get_or_create_roles(db: AsyncSession):
    """
    Get or create the necessary roles (OWNER and MEMBER).
    Returns a dict with role names as keys and role objects as values.
    """
    roles = {}
    
    # Check if roles exist
    owner_role = await db.execute(select(Role).where(Role.name == "owner"))
    owner_role = owner_role.scalar_one_or_none()
    
    member_role = await db.execute(select(Role).where(Role.name == "member"))
    member_role = member_role.scalar_one_or_none()
    
    # Create owner role if it doesn't exist
    if not owner_role:
        owner_role = Role(
            id=uuid.uuid4(),
            name="owner",
            description="Organization owner with full permissions",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(owner_role)
        await db.flush()
    
    # Create member role if it doesn't exist
    if not member_role:
        member_role = Role(
            id=uuid.uuid4(),
            name="member",
            description="Organization member with standard permissions",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(member_role)
        await db.flush()
    
    roles["owner"] = owner_role
    roles["member"] = member_role
    
    return roles


async def create_mock_data(db: AsyncSession):
    """
    Create all required mock data for testing ticket invitations.

    Returns a dictionary with all created entities for easy reference.
    """
    print("🔧 Creating mock data...\n")

    # 0. Clean up any existing test users first
    print("🧹 Checking for existing test users...")
    existing_admin = await db.execute(
        select(User).where(User.email == "admin@testlegalfirm.com")
    )
    existing_admin = existing_admin.scalar_one_or_none()
    
    existing_internal = await db.execute(
        select(User).where(User.email == "internal@testlegalfirm.com")
    )
    existing_internal = existing_internal.scalar_one_or_none()
    
    if existing_admin or existing_internal:
        print("⚠️  Found existing test users, cleaning them up...")
        if existing_admin:
            # Delete related memberships first
            memberships = await db.execute(
                select(UserOrganization).where(UserOrganization.user_id == existing_admin.id)
            )
            for membership in memberships.scalars():
                await db.delete(membership)
            await db.delete(existing_admin)
            
        if existing_internal:
            memberships = await db.execute(
                select(UserOrganization).where(UserOrganization.user_id == existing_internal.id)
            )
            for membership in memberships.scalars():
                await db.delete(membership)
            await db.delete(existing_internal)
        
        await db.commit()
        print("✅ Cleaned up existing test users")

    # 1. Get or create roles
    print("📋 Setting up roles...")
    roles = await get_or_create_roles(db)
    print(f"✅ Roles ready: {list(roles.keys())}")

    # 1. Create Organization
    org = Organization(
        id=uuid.uuid4(),
        name="Test Legal Firm",
        slug="test-legal-firm",
        email="contact@testlegalfirm.com",
        industry="Legal Services",
        state="active",
        description="Test organization for ticket invitations",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(org)
    await db.flush()
    print(f"✅ Created Organization: {org.name} (ID: {org.id})")

    # 2. Create Users
    # Hash passwords using bcrypt directly
    print("🔐 Hashing passwords with bcrypt...")
    admin_password_hash = hash_password("password123")
    internal_password_hash = hash_password("password123")
    print("✅ Passwords hashed successfully")
    
    # User 1: Admin who will create the ticket and invite others
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@testlegalfirm.com",
        name="Admin User",
        hashed_password=admin_password_hash,
        auth_provider="local",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(admin_user)

    # User 2: Internal team member (will be invited)
    internal_user = User(
        id=uuid.uuid4(),
        email="internal@testlegalfirm.com",
        name="Internal Team Member",
        hashed_password=internal_password_hash,
        auth_provider="local",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(internal_user)

    await db.flush()
    print(f"✅ Created Admin User: {admin_user.email} (ID: {admin_user.id})")
    print(f"✅ Created Internal User: {internal_user.email} (ID: {internal_user.id})")

    # 3. Create UserOrganization memberships
    admin_membership = UserOrganization(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        organization_id=org.id,
        role_id=roles["owner"].id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(admin_membership)

    internal_membership = UserOrganization(
        id=uuid.uuid4(),
        user_id=internal_user.id,
        organization_id=org.id,
        role_id=roles["member"].id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(internal_membership)
    await db.flush()
    print("✅ Created organization memberships for both users")

    # 4. Create Project
    project = Project(
        id=uuid.uuid4(),
        title="Contract Management System",
        description="Project for managing legal contracts",
        org_id=org.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.flush()
    print(f"✅ Created Project: {project.title} (ID: {project.id})")

    # 5. Create Ticket
    ticket = Ticket(
        id=uuid.uuid4(),
        title="Legal Review Required for Contract Amendment",
        description="We need external legal counsel to review the proposed contract amendments",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
        is_manual=True,
        organization_id=org.id,
        project_id=project.id,
        created_by_user_id=admin_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(ticket)
    await db.commit()
    print(f"✅ Created Ticket: {ticket.title} (ID: {ticket.id})")

    print("\n" + "=" * 80)
    print("📊 Mock Data Summary")
    print("=" * 80)

    return {
        "organization": org,
        "admin_user": admin_user,
        "internal_user": internal_user,
        "project": project,
        "ticket": ticket,
        "roles": roles,
    }


async def login_user(email: str, password: str) -> str:
    """
    Login a user and return the access token.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": email, "password": password},
        )

        if response.status_code == 200:
            data = response.json()
            return data["data"]["access_token"]
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text}")


async def test_invite_participants(
    ticket_id: uuid.UUID,
    access_token: str,
    organization_id: uuid.UUID
):
    """
    Test inviting participants to a ticket (both internal users and external guests).
    """
    print("\n" + "=" * 80)
    print("🧪 Testing Ticket Invitation")
    print("=" * 80)

    # Test payload: Mix of internal users and external participants
    payload = {
        "organization_id": str(organization_id),  # ← Add this line
        "emails": [
            "internal@testlegalfirm.com",
            "counsel@externallawfirm.com",
            "consultant@advisory.com",
        ],
        "role": "Legal Counsel",
        "expiry_days": 7,
    }

    print(f"\n📤 Sending invitation request to ticket: {ticket_id}")
    print(f"Emails to invite: {payload['emails']}")
    print(f"Role (for external): {payload['role']}")
    print(f"Expiry (for external): {payload['expiry_days']} days")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/tickets/{ticket_id}/invitations",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

        print(f"\n📥 Response Status: {response.status_code}")

        if response.status_code == 201:
            data = response.json()
            print("\n✅ Invitation successful!")
            print("\n" + "-" * 80)
            print("📊 Results:")
            print("-" * 80)

            # Internal users
            internal_users = data["data"]["internal_users"]
            if internal_users:
                print(f"\n👥 Internal Users Notified ({len(internal_users)}):")
                for user in internal_users:
                    print(f"   • {user['email']} ({user['name']})")
                    print("     - Type: Internal user (will log in normally)")
                    print(f"     - Invited at: {user['invited_at']}")

            # External participants
            external_participants = data["data"]["external_participants"]
            if external_participants:
                print(f"\n🌐 External Participants Invited ({len(external_participants)}):")
                for participant in external_participants:
                    print(f"   • {participant['email']}")
                    print(f"     - Role: {participant['role']}")
                    print("     - Type: Guest access (magic link)")
                    print(f"     - Expires at: {participant['expires_at']}")
                    print(f"     - Magic link: {participant['magic_link']}")

            # Already invited
            already_invited = data["data"]["already_invited"]
            if already_invited:
                print(f"\n⚠️  Already Invited ({len(already_invited)}):")
                for email in already_invited:
                    print(f"   • {email}")

            print("\n" + "=" * 80)

            # Return magic link for guest access testing
            if external_participants:
                return external_participants[0]["magic_link"]
        else:
            print("\n❌ Invitation failed!")
            print(f"Error: {response.text}")
            return None


async def test_guest_access(magic_link: str):
    """
    Test guest access using the magic link.
    """
    print("\n" + "=" * 80)
    print("🔐 Testing Guest Access (Magic Link)")
    print("=" * 80)

    # Extract token from magic link
    if "token=" in magic_link:
        token = magic_link.split("token=")[1]
        print(f"\n🎫 Extracted token: {token[:50]}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/tickets/external/access",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )

            print(f"\n📥 Response Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("\n✅ Guest access validated successfully!")
                print("\n" + "-" * 80)
                print("📊 Ticket Details (Guest View):")
                print("-" * 80)

                ticket_data = data["data"]
                print(f"   • Ticket ID: {ticket_data['ticket_id']}")
                print(f"   • Title: {ticket_data['title']}")
                print(f"   • Description: {ticket_data['description']}")
                print(f"   • Status: {ticket_data['status']}")
                print(f"   • Priority: {ticket_data['priority']}")
                print(f"   • Project: {ticket_data['project_name']}")
                print("\n   Guest Info:")
                print(f"   • Email: {ticket_data['participant_email']}")
                print(f"   • Role: {ticket_data['participant_role']}")
                print(f"   • Access Expires: {ticket_data['access_expires_at']}")

                print("\n" + "=" * 80)
            else:
                print("\n❌ Guest access failed!")
                print(f"Error: {response.text}")
    else:
        print("\n❌ Invalid magic link format")


async def cleanup_mock_data(mock_data: dict):
    """
    Optional: Clean up the mock data after testing.
    """
    print("\n" + "=" * 80)
    print("🧹 Cleaning up mock data...")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        # Delete ticket (cascades to external_participants)
        await db.delete(mock_data["ticket"])

        # Delete project
        await db.delete(mock_data["project"])

        # Delete user memberships
        result = await db.execute(
            select(UserOrganization).where(
                UserOrganization.organization_id == mock_data["organization"].id
            )
        )
        memberships = result.scalars().all()
        for membership in memberships:
            await db.delete(membership)

        # Delete users
        await db.delete(mock_data["admin_user"])
        await db.delete(mock_data["internal_user"])

        # Delete organization
        await db.delete(mock_data["organization"])

        await db.commit()

    print("✅ Mock data cleaned up successfully")


async def main():
    """
    Main test flow.
    """
    print("\n" + "=" * 80)
    print("🚀 Ticket Invitation System Test (Using bcrypt directly)")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Create mock data (organization, users, project, ticket)")
    print("2. Test inviting participants (internal users + external guests)")
    print("3. Test guest access using magic link")
    print("4. Optionally clean up the mock data")
    print("=" * 80)

    # Step 1: Create mock data
    async with AsyncSessionLocal() as db:
        mock_data = await create_mock_data(db)

    # Print test credentials
    print("\n" + "=" * 80)
    print("🔑 Test Credentials")
    print("=" * 80)
    print("Admin Email: admin@testlegalfirm.com")
    print("Admin Password: password123")
    print("Internal User Email: internal@testlegalfirm.com")
    print("Internal User Password: password123")
    print("=" * 80)

    # Step 2: Login as admin
    print("\n🔐 Logging in as admin user...")
    try:
        access_token = await login_user("admin@testlegalfirm.com", "password123")
        print("✅ Login successful!")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        print(f"\n⚠️  Make sure the server is running at: {API_BASE_URL}")
        return

    # Step 3: Test invitation
    magic_link = await test_invite_participants(
        mock_data["ticket"].id, 
        access_token,
        mock_data["organization"].id  # ← Add this parameter
    )

    # Step 4: Test guest access (if we got a magic link)
    if magic_link:
        await test_guest_access(magic_link)

    # Step 5: Ask if user wants to clean up
    print("\n" + "=" * 80)
    cleanup = input("\n🧹 Do you want to clean up the mock data? (y/n): ")
    if cleanup.lower() == "y":
        await cleanup_mock_data(mock_data)
    else:
        print("\n📝 Mock data preserved. You can use it for manual testing:")
        print(f"   • Organization ID: {mock_data['organization'].id}")
        print(f"   • Ticket ID: {mock_data['ticket'].id}")
        print(f"   • Admin User ID: {mock_data['admin_user'].id}")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(main())