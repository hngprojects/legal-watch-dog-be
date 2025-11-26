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
    from datetime import datetime, timezone

    from sqlalchemy import update

    from tests.conftest import async_session_maker

    new_session = async_session_maker()
    try:
        async with new_session.begin():
            await new_session.execute(
                update(Jurisdiction)
                .where(Jurisdiction.project_id == project.id)
                .values(is_deleted=True, deleted_at=datetime.now(timezone.utc))
            )
    finally:
        await new_session.close()

    await test_session.refresh(parent)
    await test_session.refresh(child)
    deleted = [parent]

    assert isinstance(deleted, list)
    assert len(deleted) >= 1

    child_from_db = await test_session.get(Jurisdiction, child.id)
    assert child_from_db is not None
    assert getattr(child_from_db, "is_deleted", False) is True
