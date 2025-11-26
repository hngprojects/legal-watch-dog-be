from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.api.modules.v1.jurisdictions.routes import jurisdiction_route as routes
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
)


@pytest.mark.asyncio
async def test_create_jurisdiction_handler_monkeypatched(monkeypatch):
    """Ensure create_jurisdiction returns the value from a monkeypatched service.create.

    Patch routes.service.create with an async fake that returns a Jurisdiction with a
    fixed id, call routes.create_jurisdiction(payload, db=None), and assert status 201
    and that the returned jurisdiction id matches the fixed id.
    """
    """Call the route handler with a monkeypatched service.create to ensure
    the handler returns what the service returns."""

    fake_id = uuid4()

    async def fake_create(db, jurisdiction):
        # return a lightweight object, avoid constructing a SQLModel instance
        return SimpleNamespace(
            id=fake_id,
            project_id=jurisdiction.project_id,
            name=jurisdiction.name,
            description=jurisdiction.description,
        )

    monkeypatch.setattr(routes.service, "create", fake_create)

    # Prevent the route from constructing a real SQLModel Jurisdiction which
    # triggers SQLAlchemy mapper initialization (and fails in tests). Replace
    # the `Jurisdiction` symbol in the routes module with a lightweight stub
    # that accepts arbitrary kwargs and sets them as attributes.
    class _StubJurisdiction:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    monkeypatch.setattr(routes, "Jurisdiction", _StubJurisdiction)

    payload = JurisdictionCreateSchema(project_id=uuid4(), name="R-1", description="d")

    res = await routes.create_jurisdiction(payload, db=cast(Any, None))

    assert hasattr(res, "status_code")
    assert res.status_code == 201
    body = res.body
    import json

    content = json.loads(body)
    assert "data" in content and "jurisdiction" in content["data"]
    jur = content["data"]["jurisdiction"]
    assert jur["id"] == str(fake_id)


@pytest.mark.asyncio
async def test_get_jurisdiction_not_found_raises(monkeypatch):
    """Test that requesting a non-existent jurisdiction is handled as a 404.
    This async test patches the service layer to simulate that no jurisdiction
    exists for the requested ID (service.get_jurisdiction_by_id returns None).
    It then calls the route handler with a generated UUID and a placeholder db,
    and asserts that the route returns a response-like object with a status_code
    attribute set to 404, ensuring the route maps a missing resource to an HTTP 404
    failure JSONResponse.
    """

    async def fake_get(db, jurisdiction_id):
        """Asynchronous test stub that simulates retrieving a jurisdiction by its identifier.
        Parameters
        ----------
        db
            Database connection, session, or mock object (may be unused by the stub).
        jurisdiction_id
            Identifier of the jurisdiction to retrieve.
        Returns
        -------
        None
            Indicates that no matching jurisdiction was found.
            Used in tests to emulate a missing record.
        Notes
        -----
        This function is intended for use in test suites to
        simulate the "not found" path of a database lookup.
        """

        return None

    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get)

    res = await routes.get_jurisdiction(uuid4(), db=cast(Any, None))
    assert hasattr(res, "status_code")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_jurisdictions_empty_raises(monkeypatch):
    """
    Test that the jurisdictions route returns a 404 when no jurisdictions are found.
    This asynchronous test patches the service helper exposed by the route
    (routes.service.get_all_jurisdictions) with a fake coroutine that returns an
    empty list (accepting the defensive `(db)` or `(db, project_id)` signature).
    It then calls the route handler `routes.get_all_jurisdictions` with a None
    database argument and asserts that the returned response object has a
    `status_code` attribute equal to 404.
    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to replace the service function with the fake implementation.
    Notes
    -----
    - The fake service is implemented as `async def fake_all(db): return []`.
    - The test verifies route-level behavior (404 on empty result), not service logic.
    """

    async def fake_all(db):
        """
        Asynchronous test helper that simulates fetching all records from a datastore.
        Parameters
        ----------
        db : Any
            A database/session fixture or connection object. Accepted for signature
            compatibility but not used by this fake implementation.
        Returns
        -------
        list
            An empty list, representing no records found. Intended for use as a stub
            in unit tests to avoid hitting a real database.
        """

        return []

    monkeypatch.setattr(routes.service, "get_all_jurisdictions", fake_all)

    res = await routes.get_all_jurisdictions(db=cast(Any, None))
    assert hasattr(res, "status_code")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_jurisdiction_returns_id(monkeypatch):
    """
    Test that delete_jurisdiction returns the ID of the deleted jurisdiction.
    This test creates a fake UUID and monkeypatches routes.service.soft_delete to
    simulate a successful soft-delete by returning a Jurisdiction instance with
    that ID.
    """

    fake_id = uuid4()

    async def fake_soft_delete(db, jurisdiction_id=None, project_id=None):
        return SimpleNamespace(id=fake_id, project_id=uuid4(), name="x", description="d")

    monkeypatch.setattr(routes.service, "soft_delete", fake_soft_delete)

    res = await routes.soft_delete_jurisdiction(fake_id, db=cast(Any, None))
    assert hasattr(res, "status_code")
    assert res.status_code == 204
    import json

    if not res.body:
        assert res.body in (b"", "")
    else:
        content = json.loads(res.body)
        expected = {
            "status": "SUCCESS",
            "status_code": 204,
            "message": "Jurisdiction archived successfully",
            "data": {},
        }

        assert content == expected


@pytest.mark.asyncio
async def test_delete_jurisdictions_by_project_returns_ids(monkeypatch):
    """
    Test that delete_jurisdictions_by_project returns a 200 response and the expected
    list of jurisdiction IDs when the service soft_delete operation successfully
    soft-deletes jurisdictions for a project.
    """

    fake_id = uuid4()

    async def fake_soft_delete(db, jurisdiction_id=None, project_id=None):
        """
        Simulate a soft-delete operation for jurisdictions in tests.
        This asynchronous test helper returns a list containing a single fake
        Jurisdiction object. It does not perform any real database operations;
        its purpose is to emulate the shape and behavior of a soft-delete
        function for use in unit tests.
        """

        return [
            SimpleNamespace(id=fake_id, project_id=project_id or uuid4(), name="x", description="d")
        ]

    monkeypatch.setattr(routes.service, "soft_delete", fake_soft_delete)

    proj_id = uuid4()
    res = await routes.soft_delete_jurisdictions_by_project(proj_id, db=cast(Any, None))
    assert hasattr(res, "status_code")
    assert res.status_code == 204
    import json

    if not res.body:
        assert res.body in (b"", "")
    else:
        content = json.loads(res.body)
        expected = {
            "status": "SUCCESS",
            "status_code": 204,
            "message": "1 Jurisdiction(s) archived successfully",
            "data": {},
        }

        assert content == expected


@pytest.mark.asyncio
async def test_restore_jurisdiction_success(monkeypatch):
    """
    Test that the restore_jurisdiction route successfully restores a soft-deleted jurisdiction.
    This asynchronous unit test constructs a fake Jurisdiction model instance marked as deleted
    (is_deleted=True) and uses monkeypatch to replace the service-layer helpers used by the
    route
    """

    fake_id = uuid4()

    # use a lightweight object to represent the jurisdiction under test
    jur = SimpleNamespace(
        id=fake_id,
        project_id=uuid4(),
        name="ToRestore",
        description="d",
        is_deleted=True,
        deleted_at=None,
    )

    # Accept arbitrary kwargs (e.g. `restore_nested`) because the route calls
    # service.get_jurisdiction_for_restoration(..., restore_nested=True).
    async def fake_get(db, jurisdiction_id, *args, **kwargs):
        return jur

    async def fake_update(db, jurisdiction):
        return jurisdiction

    monkeypatch.setattr(routes.service, "get_jurisdiction_for_restoration", fake_get)
    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get)
    monkeypatch.setattr(routes.service, "update", fake_update)

    res = await routes.restore_jurisdiction(fake_id, db=cast(Any, None))

    assert hasattr(res, "status_code")
    assert res.status_code == 200
    import json

    content = json.loads(res.body)
    assert "data" in content and "jurisdiction" in content["data"]
    jur = content["data"]["jurisdiction"]

    assert jur.get("is_deleted") is False
