import json
from unittest.mock import MagicMock, patch

import pytest

from app.api.modules.v1.auth.routes.apple_auth_route import apple_login
from app.api.modules.v1.auth.schemas.apple_auth import AppleAuthRequest


@pytest.mark.asyncio
async def test_apple_login_success():
    req = AppleAuthRequest(code="abc123")
    fake_db = MagicMock()

    fake_result = {
        "access_token": "app.jwt",
        "user_id": "1",
        "email": "u@ex.com",
        "is_new_user": False,
    }

    class DummyClient:
        def __init__(self, db):
            pass

        async def complete_oauth_flow(self, code, redirect_uri=None):
            return fake_result

    with patch("app.api.modules.v1.auth.routes.apple_auth_route.AppleAuthClient", DummyClient):
        resp = await apple_login(req, db=fake_db)

    assert resp is not None
    import json

    data = json.loads(resp.body.decode())
    assert data["status"] == "SUCCESS"
    assert data["data"]["email"] == "u@ex.com"


@pytest.mark.asyncio
async def test_apple_login_failure_returns_error():
    req = AppleAuthRequest(code="bad")
    fake_db = MagicMock()

    class DummyClientBad:
        def __init__(self, db):
            pass

        async def complete_oauth_flow(self, code, redirect_uri=None):
            raise ValueError("Invalid token")

    with patch("app.api.modules.v1.auth.routes.apple_auth_route.AppleAuthClient", DummyClientBad):
        resp = await apple_login(req, db=fake_db)

    assert resp is not None

    data = json.loads(resp.body.decode())
    assert (
        "invalid" in data["error"].lower()
        or "invalid" in data["message"].lower()
        or "token" in data["error"].lower()
    )
