from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.routes import jurisdiction_route as routes
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
)


@pytest.mark.asyncio
async def test_create_jurisdiction_handler_monkeypatched(monkeypatch):
    """Call the route handler with a monkeypatched service.create to ensure
    the handler returns what the service returns."""

    fake_id = uuid4()

    async def fake_create(db, jurisdiction):
        # return a Jurisdiction-like object
        return Jurisdiction(
            id=fake_id,
            project_id=jurisdiction.project_id,
            name=jurisdiction.name,
            description=jurisdiction.description,
        )

    monkeypatch.setattr(routes.service, "create", fake_create)

    payload = JurisdictionCreateSchema(project_id=uuid4(), name="R-1", description="d")

    res = await routes.create_jurisdiction(payload, db=cast(Any, None))

    assert isinstance(res, Jurisdiction)
    assert res.id == fake_id


@pytest.mark.asyncio
async def test_get_jurisdiction_not_found_raises(monkeypatch):
    async def fake_get(db, jurisdiction_id):
        return None

    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get)

    with pytest.raises(HTTPException):
        await routes.get_jurisdiction(uuid4(), db=cast(Any, None))


@pytest.mark.asyncio
async def test_get_jurisdictions_empty_raises(monkeypatch):
    async def fake_all(db):
        return []

    monkeypatch.setattr(routes.service, "get_all_jurisdictions", fake_all)

    with pytest.raises(HTTPException):
        # call without project_id -> will call get_all_jurisdictions
        await routes.get_jurisdictions(project_id=None, db=cast(Any, None))


@pytest.mark.asyncio
async def test_restore_jurisdiction_success(monkeypatch):
    fake_id = uuid4()

    jur = Jurisdiction(
        id=fake_id,
        project_id=uuid4(),
        name="ToRestore",
        description="d",
        is_deleted=True,
    )

    async def fake_get(db, jurisdiction_id):
        return jur

    async def fake_update(db, jurisdiction):
        return jurisdiction

    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get)
    monkeypatch.setattr(routes.service, "update", fake_update)

    restored = await routes.restore_jurisdiction(fake_id, db=cast(Any, None))
    assert restored is not None
    assert restored.is_deleted is False
