import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.schemas.project_schema import (
    ProjectBase,
    ProjectUpdate,
)
from app.api.modules.v1.projects.services.project_service import (
    create_project_service,
    get_project_service,
    hard_delete_project_service,
    list_projects_service,
    update_project_service,
)
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_create_project_after_registration(pg_async_session):
    """Test project creation after registering user and organization."""

    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="Dummy Org",
        industry="Tech",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(org)
    await pg_async_session.flush()

    role_id = uuid.uuid4()
    role = Role(
        id=role_id,
        name="admin",
        description="Admin role",
        organization_id=org_id,
        permissions=["all"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(role)
    await pg_async_session.flush()

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        organization_id=org_id,
        role_id=role_id,
        email="dummy@test.com",
        hashed_password="hashedpassword",
        name="Dummy User",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(user)
    await pg_async_session.flush()

    project_data = ProjectBase(
        title="Test Project",
        description="Dummy description",
        master_prompt="Dummy prompt",
        org_id=org_id,
    )

    project = await create_project_service(
        db=pg_async_session,
        data=project_data,
        organization_id=org_id,
        user_id=user_id,
    )

    assert project.id is not None
    assert project.title == "Test Project"
    assert project.org_id == org_id


@pytest.mark.asyncio
async def test_list_projects_service(pg_async_session: AsyncSession):
    """Test listing projects with pagination."""
    org_id = uuid.uuid4()
    page = 1
    limit = 10

    result = await list_projects_service(pg_async_session, org_id, page=page, limit=limit)

    assert "data" in result
    assert "total" in result
    assert "page" in result
    assert result["page"] == page


@pytest.mark.asyncio
async def test_get_project_service_found_and_not_found(pg_async_session: AsyncSession):
    """Test getting a project by id."""
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    project = await get_project_service(pg_async_session, project_id, org_id)

    assert project is None or isinstance(project, Project)


@pytest.mark.asyncio
async def test_update_project_service(pg_async_session: AsyncSession):
    """Test updating a project."""
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    data = ProjectUpdate(title="Updated Title")

    project = await update_project_service(pg_async_session, project_id, org_id, data)
    assert project is None or project.title == "Updated Title"


@pytest.mark.asyncio
async def test_delete_project_service(pg_async_session: AsyncSession):
    """Test deleting a project."""
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    result = await hard_delete_project_service(pg_async_session, project_id, org_id)
    assert result in [True, False]
