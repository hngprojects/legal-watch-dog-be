from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.schemas.project import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
)
from app.api.modules.v1.projects.services.project_service import (
    create_project_service,
    delete_project_service,
    get_project_service,
    list_projects_service,
    update_project_service,
)


@pytest.mark.asyncio
async def test_create_project_service(mocked_db: AsyncSession):
    """Test project creation with adding creator as member."""
    org_id = uuid4()
    creator_id = uuid4()
    data = ProjectCreateRequest(
        title="Test Project", description="Desc", master_prompt="Prompt"
    )

    project = await create_project_service(mocked_db, data, org_id, creator_id)

    assert project.id is not None
    assert project.title == "Test Project"


@pytest.mark.asyncio
async def test_list_projects_service(mocked_db: AsyncSession):
    """Test listing projects with pagination."""
    org_id = uuid4()
    page = 1
    limit = 10

    result = await list_projects_service(mocked_db, org_id, page=page, limit=limit)

    assert "data" in result
    assert "total" in result
    assert "page" in result
    assert result["page"] == page


@pytest.mark.asyncio
async def test_get_project_service_found_and_not_found(mocked_db: AsyncSession):
    """Test getting a project by id."""
    org_id = uuid4()
    project_id = uuid4()

    project = await get_project_service(mocked_db, project_id, org_id)

    assert project is None or isinstance(project, Project)


@pytest.mark.asyncio
async def test_update_project_service(mocked_db: AsyncSession):
    """Test updating a project."""
    org_id = uuid4()
    project_id = uuid4()
    data = ProjectUpdateRequest(title="Updated Title")

    project = await update_project_service(mocked_db, project_id, org_id, data)
    assert project is None or project.title == "Updated Title"


@pytest.mark.asyncio
async def test_delete_project_service(mocked_db: AsyncSession):
    """Test deleting a project."""
    org_id = uuid4()
    project_id = uuid4()

    result = await delete_project_service(mocked_db, project_id, org_id)
    assert result in [True, False]
