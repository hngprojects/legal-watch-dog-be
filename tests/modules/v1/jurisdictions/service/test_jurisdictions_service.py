import pytest
from datetime import datetime
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import JurisdictionService
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project


@pytest.mark.asyncio
async def test_create_first_jurisdiction_sets_parent(test_session):
    """Creating the first jurisdiction for a project should set its parent_id to itself."""
    svc = JurisdictionService()

    # create organization and project
    org = Organization(name="Test Org")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="P1")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    jur = Jurisdiction(project_id=project.id, name="J-First", description="d1")

    created = await svc.create(test_session, jur)

    assert created is not None
    assert created.parent_id == created.id


@pytest.mark.asyncio
async def test_create_second_jurisdiction_has_no_self_parent(test_session):
    svc = JurisdictionService()

    org = Organization(name="Test Org 2")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="P2")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    # first jurisdiction
    first = Jurisdiction(project_id=project.id, name="J-A", description="d")
    created_first = await svc.create(test_session, first)

    # second jurisdiction
    second = Jurisdiction(project_id=project.id, name="J-B", description="d")
    created_second = await svc.create(test_session, second)

    assert created_second is not None
    # second jurisdiction should not have parent_id equal to its own id
    assert created_second.parent_id != created_second.id


@pytest.mark.asyncio
async def test_get_by_name_and_delete_and_read(test_session):
    svc = JurisdictionService()

    org = Organization(name="Test Org 3")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="P3")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    jur = Jurisdiction(project_id=project.id, name="FindMe", description="d")
    created = await svc.create(test_session, jur)

    found = await svc.get_jurisdiction_by_name(test_session, "FindMe")
    assert found is not None
    assert found.id == created.id

    all_j = await svc.read(test_session)
    assert any(x.id == created.id for x in all_j)

    deleted = await svc.delete(test_session, created)
    assert deleted is True
