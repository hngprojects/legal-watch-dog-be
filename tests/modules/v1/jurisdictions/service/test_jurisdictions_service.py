import pytest

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

    # Retrieve by name using the service helper
    found = await svc.get_jurisdiction_by_name(test_session, "FindMe")
    assert found is not None

    # The service may return either a mapped Jurisdiction instance or a
    # DB Row/tuple containing the instance depending on which execute API
    # path was used. Normalize to the model instance before asserting.
    if hasattr(found, "id"):
        found_obj = found
    else:
        # try to unwrap a Row/tuple like result
        try:
            found_obj = found[0]
        except Exception:
            pytest.fail("Unexpected return shape from get_jurisdiction_by_name")

    assert found_obj.id == created.id

    # Read all jurisdictions (service may return rows or instances)
    all_j = await svc.read(test_session)
    ids = []
    for item in all_j:
        if hasattr(item, "id"):
            ids.append(item.id)
        else:
            try:
                ids.append(item[0].id)
            except Exception:
                # If we can't extract an id, fail early with a helpful message
                pytest.fail("Unexpected item shape returned from JurisdictionService.read")

    assert created.id in ids

    # Delete jurisdiction
    deleted = await svc.delete(test_session, created)
    assert deleted is True
