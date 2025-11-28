from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.config import settings
from app.api.modules.v1.auth.service.apple_auth import AppleAuthClient
from app.api.modules.v1.users.models.users_model import User


def _set_apple_env(monkeypatch):
    # The service reads values from settings, patch them here
    monkeypatch.setattr(settings, "APPLE_TEAM_ID", "team-id", raising=False)
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "client-id", raising=False)
    monkeypatch.setattr(settings, "APPLE_KEY_ID", "key-id", raising=False)
    monkeypatch.setattr(settings, "APPLE_PRIVATE_KEY", "-private-key-", raising=False)
    monkeypatch.setattr(settings, "APPLE_CLIENT_SECRET_LIFETIME", 3600, raising=False)


def test_generate_apple_client_secret(monkeypatch):
    _set_apple_env(monkeypatch)

    with patch("app.api.modules.v1.auth.service.apple_auth.jwt.encode") as mock_encode:
        mock_encode.return_value = "signed-token"
        client = AppleAuthClient(db=MagicMock())

        token = client.generate_apple_client_secret()

    assert isinstance(token, str)
    assert token == "signed-token"


def test_exchange_code_for_tokens_posts(monkeypatch):
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    with patch.object(client, "generate_apple_client_secret", return_value="secret"):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id_token": "id.123", "access_token": "acc"}

        with patch(
            "app.api.modules.v1.auth.service.apple_auth.requests.post", return_value=mock_resp
        ) as mock_post:
            out = client.exchange_code_for_tokens("auth-code-1", redirect_uri="https://app/cb")

    mock_post.assert_called_once()
    assert out["id_token"] == "id.123"


def test_verify_id_token_uses_jwks_and_decode(monkeypatch):
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    fake_signing_key = MagicMock()
    fake_signing_key.key = "public-key"

    with patch("app.api.modules.v1.auth.service.apple_auth.PyJWKClient") as mock_jwks:
        inst = mock_jwks.return_value
        inst.get_signing_key_from_jwt.return_value = fake_signing_key

        with patch("app.api.modules.v1.auth.service.apple_auth.decode") as mock_decode:
            mock_decode.return_value = {"sub": "apple-1", "email": "a@b.com"}

            data = client.verify_id_token("some-token")

    assert data["sub"] == "apple-1"


@pytest.mark.asyncio
async def test_get_or_create_user_creates_and_returns_user(monkeypatch):
    _set_apple_env(monkeypatch)

    # Prepare a fake Async DB that reports no existing user
    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = None
    result.scalars.return_value = scalars
    db.execute.return_value = result

    # Ensure commit/refresh are awaitable
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    client = AppleAuthClient(db=db)

    user_info = {"sub": "apple-sub", "email": "new@apple.test", "name": "Apple Test"}

    user, is_new = await client.get_or_create_user(user_info)

    assert is_new is True
    assert isinstance(user, User)
    assert user.email == "new@apple.test"


@pytest.mark.asyncio
async def test_complete_oauth_flow_success(monkeypatch):
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    # prepare get_or_create_user to return a user
    fake_user = MagicMock(id=123, email="ok@a.com")

    client = AppleAuthClient(db=db)

    with (
        patch.object(client, "exchange_code_for_tokens", return_value={"id_token": "id-1"}),
        patch.object(
            client,
            "verify_id_token",
            return_value={"sub": "apple-xyz", "email": "ok@a.com", "name": "Ok"},
        ),
        patch.object(client, "get_or_create_user", AsyncMock(return_value=(fake_user, True))),
        patch(
            "app.api.modules.v1.auth.service.apple_auth.create_access_token", return_value="app.jwt"
        ),
    ):
        result = await client.complete_oauth_flow("code-123", redirect_uri="https://app/cb")

    assert result["access_token"] == "app.jwt"
    assert result["email"] == "ok@a.com"
    assert result["is_new_user"] is True


@pytest.mark.asyncio
async def test_complete_oauth_flow_raises_when_no_id_token(monkeypatch):
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    client = AppleAuthClient(db=db)

    with patch.object(client, "exchange_code_for_tokens", return_value={}):
        with pytest.raises(ValueError):
            await client.complete_oauth_flow("code-123", redirect_uri="https://app/cb")
