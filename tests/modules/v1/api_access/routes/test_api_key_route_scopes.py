from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.modules.v1.api_access.enums.api_key_scope import Scopes
from app.api.modules.v1.api_access.routes import api_key_route


@pytest.mark.asyncio
async def test_get_api_key_scopes_authorized(monkeypatch):
    org_id = uuid4()

    monkeypatch.setattr(api_key_route.service, "can_generate_key", lambda perms: True)

    result = await api_key_route.get_api_key_scopes(org_id, current_user_permissions={})

    assert isinstance(result, list)
    values = {r.value for r in result}
    expected = {s.value for s in Scopes}
    assert values == expected


@pytest.mark.asyncio
async def test_get_api_key_scopes_forbidden(monkeypatch):
    org_id = uuid4()

    monkeypatch.setattr(api_key_route.service, "can_generate_key", lambda perms: False)

    with pytest.raises(HTTPException) as excinfo:
        await api_key_route.get_api_key_scopes(org_id, current_user_permissions={})

    assert excinfo.value.status_code == 403
