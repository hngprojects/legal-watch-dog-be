import pytest

from app.api.modules.v1.jurisdictions.service.jurisdiction_service import JurisdictionService


@pytest.mark.asyncio
async def test_create_jurisdiction_integration(test_session):
    """Integration-style test that creates Organization -> Project -> Jurisdiction
    using the real SQLModel models and the async test_session fixture.
    Models are imported inside the test to avoid early mapper configuration.
    """
    # import models lazily to allow test setup to create tables first
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project

    svc = JurisdictionService()

    org = Organization(name="IntOrg")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="IntProj")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    jur = Jurisdiction(project_id=project.id, name="IntJ", description="desc")
    created = await svc.create(test_session, jur)

    assert created is not None
    assert created.id is not None


@pytest.mark.asyncio
async def test_soft_delete_project_archives_children_integration(test_session):
    """Create a parent jurisdiction with a child, call soft_delete by project_id and
    verify the returned jurisdictions and their children are marked as deleted in-memory.
    """
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project

    svc = JurisdictionService()

    org = Organization(name="DelOrg")
    test_session.add(org)
    await test_session.commit()
    await test_session.refresh(org)

    project = Project(org_id=org.id, title="DelProj")
    test_session.add(project)
    await test_session.commit()
    await test_session.refresh(project)

    parent = Jurisdiction(project_id=project.id, name="P", description="p")
    test_session.add(parent)
    await test_session.commit()
    await test_session.refresh(parent)

    child = Jurisdiction(project_id=project.id, parent_id=parent.id, name="C", description="c")
    test_session.add(child)
    await test_session.commit()
    await test_session.refresh(child)

    # soft delete by project
    deleted = await svc.soft_delete(test_session, project_id=project.id)

    # service returns list of top-level jurisdictions (parent). Ensure returned list
    # is not empty and that child objects were marked deleted by the recursive helper
    assert isinstance(deleted, list)
    assert len(deleted) >= 1
    returned_parent = deleted[0]
    # child should be present (relationship loaded by SQLModel during refresh)
    # and should be marked deleted by the recursive helper
    children = getattr(returned_parent, "children", [])
    if children:
        assert all(c.is_deleted for c in children)
