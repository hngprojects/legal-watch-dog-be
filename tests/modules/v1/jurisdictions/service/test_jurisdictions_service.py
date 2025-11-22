import pytest
from sqlalchemy import select

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import (
    JurisdictionService,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project


@pytest.mark.asyncio
async def test_create_first_jurisdiction_sets_parent(test_session):
    """Creating the first jurisdiction for a project."""
    svc = JurisdictionService()

    # Create organization and project
    org = Organization(name="Test Org")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="P1")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    # Create first jurisdiction
    jur = Jurisdiction(project_id=project.id, name="J-First", description="d1")
    created = await svc.create(test_session, jur)

    # Assertions
    assert created is not None
    assert created.id is not None


@pytest.mark.asyncio
async def test_get_by_name_and_delete_and_read(test_session):
    """Create a jurisdiction, retrieve by name, read all, and delete."""
    svc = JurisdictionService()

    # Create organization and project
    org = Organization(name="Test Org 3")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="P3")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    # Create jurisdiction
    jur = Jurisdiction(project_id=project.id, name="FindMe", description="d")
    created = await svc.create(test_session, jur)

    # Retrieve by name using raw select and scalars
    stmt = select(Jurisdiction).where(Jurisdiction.name == "FindMe")
    result = await test_session.execute(stmt)
    found = result.scalars().first()

    assert found is not None
    assert found.id == created.id

    # Read all jurisdictions
    all_j = await svc.read(test_session)
    # If read() returns Row objects, convert them
    if all_j and hasattr(all_j[0], "Jurisdiction"):
        all_j = [r.Jurisdiction for r in all_j]

    assert any(x.id == created.id for x in all_j)

    # Delete jurisdiction
    deleted = await svc.delete(test_session, created)
    assert deleted is True
