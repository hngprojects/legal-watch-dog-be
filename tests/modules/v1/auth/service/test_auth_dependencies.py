import pytest
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.api.core.dependencies.auth import (
    require_permission,
    require_any_permission,
    verify_organization_access,
    OrganizationFilter,
    get_current_user_with_role,
)
from app.api.modules.v1.users.models import User
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.organization.models import Organization
from app.api.utils.permissions import Permission


@pytest.mark.asyncio
async def test_require_permission_grants(pg_sync_session):
    session = pg_sync_session
    try:
        # Create organization
        org = Organization(name="Test Org")
        session.add(org)
        # sync session: use sync flush
        session.flush()

        # Create role with permission
        permissions = {Permission.CREATE_PROJECTS.value: True}
        role = Role(name="admin", organization_id=org.id, permissions=permissions)
        session.add(role)
        session.flush()

        # Create user in the organization with role
        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="perm@example.com",
            hashed_password="x",
            name="Test User",
            is_verified=True,
        )
        session.add(user)
        session.commit()

        # Permission checker dependency callable
        checker = require_permission(Permission.CREATE_PROJECTS)

        # Should not raise
        result = await checker(user_role=(user, role))
        assert result.email == user.email
    finally:
        # cleanup handled by fixture
        pass


@pytest.mark.asyncio
async def test_require_permission_denies(pg_sync_session):
    session = pg_sync_session
    try:
        # Create org/role/user, role without permission
        org = Organization(name="Other Org")
        session.add(org)
        session.flush()

        role = Role(name="viewer", organization_id=org.id, permissions={})
        session.add(role)
        session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="denied@example.com",
            hashed_password="x",
            name="Denied User",
            is_verified=True,
        )
        session.add(user)
        session.commit()

        checker = require_permission(Permission.CREATE_PROJECTS)

        with pytest.raises(HTTPException) as exc_info:
            await checker(user_role=(user, role))

    finally:
        pass


@pytest.mark.asyncio
async def test_require_any_permission(pg_sync_session):
    session = pg_sync_session
    try:
        # Create org and role with one of many permissions
        org = Organization(name="OrgAny")
        session.add(org)
        # sync session flush
        session.flush()

        permissions = {Permission.VIEW_PROJECTS.value: True}
        role = Role(name="viewer", organization_id=org.id, permissions=permissions)
        session.add(role)
        session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="any@example.com",
            hashed_password="x",
            name="Any User",
            is_verified=True,
        )
        session.add(user)
        session.commit()

        checker = require_any_permission(
            Permission.CREATE_PROJECTS, Permission.VIEW_PROJECTS
        )

        # Should succeed because the role has VIEW_PROJECTS
        result = await checker(user_role=(user, role))
        assert result.email == user.email
    finally:
        pass


@pytest.mark.asyncio
async def test_organization_access_allowed_and_denied(pg_sync_session):
    session = pg_sync_session
    try:
        org = Organization(name="Org1")
        session.add(org)
        # sync session flush
        session.flush()

        role = Role(name="admin", organization_id=org.id, permissions={})
        session.add(role)
        session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="orguser@example.com",
            hashed_password="x",
            name="Org User",
            is_verified=True,
        )
        session.add(user)
        session.commit()

        # Should pass for the same organization
        assert await verify_organization_access(str(org.id), current_user=user)

        # Should fail for a different org id
        with pytest.raises(HTTPException):
            await verify_organization_access(
                "00000000-0000-0000-0000-000000000000", current_user=user
            )
    finally:
        pass


@pytest.mark.asyncio
async def test_organization_filter(pg_sync_session):
    """Test OrganizationFilter dependency class"""
    session = pg_sync_session
    try:
        org = Organization(name="FilterOrg")
        session.add(org)
        session.flush()

        role = Role(name="editor", organization_id=org.id, permissions={})
        session.add(role)
        session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="filter@example.com",
            hashed_password="x",
            name="Filter User",
            is_verified=True,
        )
        session.add(user)
        session.commit()

        # Test OrganizationFilter
        org_filter = OrganizationFilter(current_user=user)
        assert org_filter.org_id == user.organization_id
        assert org_filter.user.email == user.email
    finally:
        pass


@pytest.mark.asyncio
async def test_get_current_user_with_role(pg_async_session):
    """Test get_current_user_with_role dependency with async session"""
    async_session = pg_async_session

    # Create org, role and user in async session
    org = Organization(name="AsyncOrg")
    async_session.add(org)
    await async_session.flush()

    role = Role(name="editor", organization_id=org.id, permissions={})
    async_session.add(role)
    await async_session.flush()

    user = User(
        organization_id=org.id,
        role_id=role.id,
        email="async@example.com",
        hashed_password="x",
        name="Async User",
        is_verified=True,
    )
    async_session.add(user)
    await async_session.commit()

    current_user, loaded_role = await get_current_user_with_role(
        current_user=user, db=async_session
    )
    assert current_user.email == user.email
    assert loaded_role.id == role.id
