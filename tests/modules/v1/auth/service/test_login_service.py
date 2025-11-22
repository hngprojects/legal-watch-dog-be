import re

import pytest
from fastapi import HTTPException

from app.api.modules.v1.auth.service.login_service import (
    MAX_LOGIN_ATTEMPTS,
    authenticate_user,
)
from app.api.modules.v1.organization.models import Organization
from app.api.modules.v1.users.models import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.utils.permissions import Permission


@pytest.mark.asyncio
async def test_successful_login_with_rate_limiting(pg_sync_session, pg_async_session):
    """Test successful login resets rate limiting counters and returns refresh token"""
    session = pg_sync_session

    # Create organization
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()

    # Create role with permissions
    permissions = {
        Permission.VIEW_PROJECTS.value: True,
        Permission.CREATE_PROJECTS.value: True,
    }
    role = Role(name="admin", organization_id=org.id, permissions=permissions)
    session.add(role)
    session.flush()

    # Create user with hashed password
    from app.api.utils.password import hash_password

    hashed_pw = hash_password("SecurePassword123!")

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="login@example.com",
        hashed_password=hashed_pw,
        name="Login User",
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.commit()

    # Authenticate using async session
    async_session = pg_async_session

    result = await authenticate_user(
        db=async_session,
        email="login@example.com",
        password="SecurePassword123!",
        ip_address="192.168.1.1",
    )

    # Verify response structure
    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert result["expires_in"] == 3600 * 24
    assert result["user"]["email"] == "login@example.com"
    assert result["user"]["role_name"] == "admin"
    assert "permissions" in result["user"]
    assert result["user"]["permissions"] == permissions


@pytest.mark.asyncio
async def test_failed_login_increments_counter(pg_sync_session, pg_async_session):
    """Test that failed login attempts increment the counter"""
    session = pg_sync_session

    org = Organization(name="Test Org")
    session.add(org)
    session.flush()

    role = Role(name="user", organization_id=org.id, permissions={})
    session.add(role)
    session.flush()

    from app.api.utils.password import hash_password

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="fail@example.com",
        hashed_password=hash_password("CorrectPassword"),
        name="Fail User",
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.commit()

    async_session = pg_async_session

    # Attempt login with wrong password
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(
            db=async_session,
            email="fail@example.com",
            password="WrongPassword",
            ip_address="192.168.1.2",
        )

    assert exc_info.value.status_code == 400
    assert "attempts remaining" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_account_lockout_after_max_attempts(pg_sync_session, pg_async_session):
    """Test account locks after MAX_LOGIN_ATTEMPTS failed attempts"""
    session = pg_sync_session

    org = Organization(name="Lockout Org")
    session.add(org)
    session.flush()

    role = Role(name="user", organization_id=org.id, permissions={})
    session.add(role)
    session.flush()

    from app.api.utils.password import hash_password

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="lockout@example.com",
        hashed_password=hash_password("CorrectPassword"),
        name="Lockout User",
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.commit()

    async_session = pg_async_session

    # Make MAX_LOGIN_ATTEMPTS failed attempts
    for i in range(MAX_LOGIN_ATTEMPTS):
        try:
            await authenticate_user(
                db=async_session, email="lockout@example.com", password="WrongPassword"
            )
        except HTTPException:
            pass

    # Next attempt should return account locked error
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(
            db=async_session, email="lockout@example.com", password="WrongPassword"
        )

    assert exc_info.value.status_code == 429
    assert "locked" in exc_info.value.detail.lower()
    assert re.search(r"\d+\s*minutes?", exc_info.value.detail, re.IGNORECASE)


@pytest.mark.asyncio
async def test_login_fails_for_inactive_user(pg_sync_session, pg_async_session):
    """Test login fails for inactive users"""
    session = pg_sync_session

    org = Organization(name="Inactive Org")
    session.add(org)
    session.flush()

    role = Role(name="user", organization_id=org.id, permissions={})
    session.add(role)
    session.flush()

    from app.api.utils.password import hash_password

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="inactive@example.com",
        hashed_password=hash_password("Password123"),
        name="Inactive User",
        is_verified=True,
        is_active=False,  # Inactive
    )
    session.add(user)
    session.commit()

    async_session = pg_async_session

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(
            db=async_session, email="inactive@example.com", password="Password123"
        )

    assert exc_info.value.status_code == 403
    assert "inactive" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_login_fails_for_unverified_user(pg_sync_session, pg_async_session):
    """Test login fails for unverified users"""
    session = pg_sync_session

    org = Organization(name="Unverified Org")
    session.add(org)
    session.flush()

    role = Role(name="user", organization_id=org.id, permissions={})
    session.add(role)
    session.flush()

    from app.api.utils.password import hash_password

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="unverified@example.com",
        hashed_password=hash_password("Password123"),
        name="Unverified User",
        is_verified=False,  # Not verified
        is_active=True,
    )
    session.add(user)
    session.commit()

    async_session = pg_async_session

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(
            db=async_session, email="unverified@example.com", password="Password123"
        )

    assert exc_info.value.status_code == 403
    assert "verify" in exc_info.value.detail.lower()
