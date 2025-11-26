from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.modules.v1.auth.service.login_service import (
    LOCKOUT_DURATION_MINUTES,
    MAX_LOGIN_ATTEMPTS,
    LoginService,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password


@pytest.mark.asyncio
async def test_successful_login_with_organizations(pg_sync_session, pg_async_session):
    """Test successful login returns tokens and multiple organizations"""
    session = pg_sync_session

    org = Organization(id="550e8400-e29b-41d4-a716-446655440000", name="Login Org")
    session.add(org)
    session.flush()

    role = Role(name="admin", permissions={"view": True})
    session.add(role)
    session.flush()

    user = User(
        email="login@example.com",
        hashed_password=hash_password("SecurePassword123!"),
        name="Login User",
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.flush()

    membership = UserOrganization(
        user_id=user.id,
        organization_id="550e8400-e29b-41d4-a716-446655440000",
        role_id=role.id,
        is_active=True,
    )
    session.add(membership)
    session.commit()

    with patch(
        "app.api.modules.v1.auth.service.login_service.get_redis_client", new_callable=AsyncMock
    ):
        service = LoginService(db=pg_async_session)
        result = await service.login(
            email="login@example.com", password="SecurePassword123!", ip_address="127.0.0.1"
        )

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert result["user"]["email"] == "login@example.com"
    assert result["user"]["has_organizations"] is True
    assert len(result["user"]["organizations"]) == 1
    org_info = result["user"]["organizations"][0]
    assert org_info["role_name"] == "admin"
    assert org_info["permissions"] == {"view": True}


@pytest.mark.asyncio
async def test_failed_login_increments_counter(pg_sync_session, pg_async_session):
    """Test failed login increments failed attempts and returns remaining attempts"""
    session = pg_sync_session

    user = User(
        email="fail@example.com",
        hashed_password=hash_password("CorrectPassword"),
        name="Fail User",
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.commit()

    with patch(
        "app.api.modules.v1.auth.service.login_service.get_redis_client", new_callable=AsyncMock
    ):
        service = LoginService(db=pg_async_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.login(email="fail@example.com", password="WrongPassword")

    assert exc_info.value.status_code == 400
    assert "attempts remaining" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_account_lockout_after_max_attempts(pg_sync_session, pg_async_session):
    """Test account locks after MAX_LOGIN_ATTEMPTS failed attempts"""
    session = pg_sync_session

    user = User(
        email="lockout@example.com",
        hashed_password=hash_password("CorrectPassword"),
        name="Lockout User",
        is_verified=True,
        is_active=True,
    )
    session.add(user)
    session.commit()

    redis_mock = AsyncMock()
    redis_mock.incr.return_value = MAX_LOGIN_ATTEMPTS
    redis_mock.ttl.return_value = LOCKOUT_DURATION_MINUTES * 60

    with patch(
        "app.api.modules.v1.auth.service.login_service.get_redis_client", return_value=redis_mock
    ):
        service = LoginService(db=pg_async_session)
        with pytest.raises(HTTPException) as exc_info:
            await service.login(email="lockout@example.com", password="WrongPassword")

    assert exc_info.value.status_code == 429
    assert "locked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_login_fails_for_inactive_user(pg_sync_session, pg_async_session):
    """Test login fails for inactive users"""
    session = pg_sync_session

    user = User(
        email="inactive@example.com",
        hashed_password=hash_password("Password123"),
        name="Inactive User",
        is_verified=True,
        is_active=False,
    )
    session.add(user)
    session.commit()

    with patch(
        "app.api.modules.v1.auth.service.login_service.get_redis_client", new_callable=AsyncMock
    ):
        service = LoginService(db=pg_async_session)
        with pytest.raises(HTTPException) as exc_info:
            await service.login(email="inactive@example.com", password="Password123")

    assert exc_info.value.status_code == 403
    assert "inactive" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_login_fails_for_unverified_user(pg_sync_session, pg_async_session):
    """Test login fails for unverified users"""
    session = pg_sync_session

    user = User(
        email="unverified@example.com",
        hashed_password=hash_password("Password123"),
        name="Unverified User",
        is_verified=False,
        is_active=True,
    )
    session.add(user)
    session.commit()

    with patch(
        "app.api.modules.v1.auth.service.login_service.get_redis_client", new_callable=AsyncMock
    ):
        service = LoginService(db=pg_async_session)
        with pytest.raises(HTTPException) as exc_info:
            await service.login(email="unverified@example.com", password="Password123")

    assert exc_info.value.status_code == 403
    assert "verify" in exc_info.value.detail.lower()
