import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response
from starlette.requests import Request

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

    mock_request = MagicMock(spec=Request)
    mock_request.url.hostname = "localhost"
    mock_request.headers = {}

    with patch("app.api.modules.v1.auth.routes.apple_auth_route.AppleAuthClient", DummyClient):
        response_obj = Response()
        resp = await apple_login(req, request=mock_request, response=response_obj, db=fake_db)

    assert resp is not None

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

    mock_request = MagicMock(spec=Request)
    mock_request.url.hostname = "localhost"
    mock_request.headers = {}

    with patch("app.api.modules.v1.auth.routes.apple_auth_route.AppleAuthClient", DummyClientBad):
        response_obj = Response()
        resp = await apple_login(req, request=mock_request, response=response_obj, db=fake_db)

    assert resp is not None

    data = json.loads(resp.body.decode())
    assert (
        "invalid" in data.get("error", "").lower()
        or "invalid" in data.get("message", "").lower()
        or "token" in data.get("error", "").lower()
    )
