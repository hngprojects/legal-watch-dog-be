import pytest
from fastapi import HTTPException

from app.api.core.dependencies.auth import (
    OrganizationFilter,
    get_current_user_with_role,
    require_any_permission,
    require_permission,
    verify_organization_access,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.permissions import Permission


@pytest.mark.asyncio
async def test_require_permission_grants(pg_async_session):
    session = pg_async_session
    try:
        # Create organization
        org = Organization(name="Test Org")
        session.add(org)
        # async session: use async flush
        await session.flush()

        # Create role with permission
        permissions = {Permission.CREATE_PROJECTS.value: True}
        role = Role(name="admin", organization_id=org.id, permissions=permissions)
        session.add(role)
        await session.flush()

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
        await session.commit()

        # Permission checker dependency callable
        checker = require_permission(Permission.CREATE_PROJECTS)

        # Should not raise
        result = await checker(user_role=(user, role))
        assert result.email == user.email
    finally:
        # cleanup handled by fixture
        pass


@pytest.mark.asyncio
async def test_require_permission_denies(pg_async_session):
    session = pg_async_session
    try:
        # Create org/role/user, role without permission
        org = Organization(name="Other Org")
        session.add(org)
        await session.flush()

        role = Role(name="viewer", organization_id=org.id, permissions={})
        session.add(role)
        await session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="denied@example.com",
            hashed_password="x",
            name="Denied User",
            is_verified=True,
        )
        session.add(user)
        await session.commit()

        checker = require_permission(Permission.CREATE_PROJECTS)

        with pytest.raises(HTTPException):
            await checker(user_role=(user, role))

    finally:
        pass


@pytest.mark.asyncio
async def test_require_any_permission(pg_async_session):
    session = pg_async_session
    try:
        # Create org and role with one of many permissions
        org = Organization(name="OrgAny")
        session.add(org)
        # async session flush
        await session.flush()

        permissions = {Permission.VIEW_PROJECTS.value: True}
        role = Role(name="viewer", organization_id=org.id, permissions=permissions)
        session.add(role)
        await session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="any@example.com",
            hashed_password="x",
            name="Any User",
            is_verified=True,
        )
        session.add(user)
        await session.commit()

        checker = require_any_permission(Permission.CREATE_PROJECTS, Permission.VIEW_PROJECTS)

        # Should succeed because the role has VIEW_PROJECTS
        result = await checker(user_role=(user, role))
        assert result.email == user.email
    finally:
        pass


@pytest.mark.asyncio
async def test_organization_access_allowed_and_denied(pg_async_session):
    session = pg_async_session
    try:
        org = Organization(name="Org1")
        session.add(org)
        # async session flush
        await session.flush()

        role = Role(name="admin", organization_id=org.id, permissions={})
        session.add(role)
        await session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="orguser@example.com",
            hashed_password="x",
            name="Org User",
            is_verified=True,
        )
        session.add(user)
        await session.commit()

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
async def test_organization_filter(pg_async_session):
    """Test OrganizationFilter dependency class"""
    session = pg_async_session
    try:
        org = Organization(name="FilterOrg")
        session.add(org)
        await session.flush()

        role = Role(name="editor", organization_id=org.id, permissions={})
        session.add(role)
        await session.flush()

        user = User(
            organization_id=org.id,
            role_id=role.id,
            email="filter@example.com",
            hashed_password="x",
            name="Filter User",
            is_verified=True,
        )
        session.add(user)
        await session.commit()

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
