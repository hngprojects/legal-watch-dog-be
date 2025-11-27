from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.modules.v1.jurisdictions.service.jurisdiction_service import JurisdictionService


class FakeResult:
    def __init__(self, scalar_none=False, scalars_list=None, first_obj=None):
        self._scalar_none = scalar_none
        self._scalars_list = scalars_list or []
        self._first = first_obj

    def scalar_one_or_none(self):
        if self._scalar_none:
            return None
        return self._first

    def scalars(self):
        return self

    def all(self):
        return self._scalars_list

    def first(self):
        return self._first


class FakeDB:
    def __init__(self, execute_result=None, get_result=None):
        self.execute_result = execute_result
        self.get_result = get_result
        self.added = []

    async def execute(self, stmt):
        return self.execute_result

    async def get(self, cls, id):
        return self.get_result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


@pytest.mark.asyncio
async def test_get_jurisdiction_by_id_not_found_raises():
    svc = JurisdictionService()
    fake_db = FakeDB(execute_result=FakeResult(scalar_none=True))
    with pytest.raises(HTTPException) as exc:
        await svc.get_jurisdiction_by_id(fake_db, uuid4())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_jurisdiction_by_id_archived_raises_410():
    svc = JurisdictionService()
    jur = SimpleNamespace(is_deleted=True)
    fake_db = FakeDB(execute_result=FakeResult(first_obj=jur))

    with pytest.raises(HTTPException) as exc:
        await svc.get_jurisdiction_by_id(fake_db, uuid4())

    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_get_jurisdictions_by_project_no_active_raises_404():
    svc = JurisdictionService()
    fake_db = FakeDB(execute_result=FakeResult(scalars_list=[]))

    with pytest.raises(HTTPException) as exc:
        await svc.get_jurisdictions_by_project(fake_db, uuid4())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_all_jurisdictions_all_archived_raises_410():
    svc = JurisdictionService()
    # create two fake jurisdictions that are archived
    j1 = SimpleNamespace(is_deleted=True)
    j2 = SimpleNamespace(is_deleted=True)
    fake_db = FakeDB(execute_result=FakeResult(scalars_list=[j1, j2]))

    with pytest.raises(HTTPException) as exc:
        await svc.get_all_jurisdictions(fake_db)

    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_soft_delete_by_id_not_found_returns_none():
    svc = JurisdictionService()
    fake_db = FakeDB(get_result=None)
    result = await svc.soft_delete(fake_db, jurisdiction_id=uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_jurisdiction_tree_and_restore_all_archived():
    svc = JurisdictionService()

    # Now test restore_all_archived_jurisdictions: two archived jurisdictions
    a1 = SimpleNamespace(id=uuid4(), is_deleted=True, children=[])
    a2 = SimpleNamespace(id=uuid4(), is_deleted=True, children=[])
    fake_db_restore = FakeDB(execute_result=FakeResult(scalars_list=[a1, a2]))

    restored = await svc.restore_all_archived_jurisdictions(fake_db_restore, project_id=uuid4())
    assert isinstance(restored, list)
    assert all(not getattr(j, "is_deleted", False) for j in restored)
