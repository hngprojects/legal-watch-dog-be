from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPError, Response

from app.api.modules.v1.auth.schemas.oauth_microsoft import MicrosoftUserInfo
from app.api.modules.v1.auth.service.oauth_microsoft import MicrosoftOAuthService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password


@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    redis_mock = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.delete = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_msal_app():
    """Create a mock MSAL application"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ) as mock:
        msal_instance = MagicMock()
        mock.return_value = msal_instance
        yield msal_instance


@pytest.fixture
def microsoft_service(pg_async_session, mock_redis, mock_msal_app):
    """Create MicrosoftOAuthService instance with mocked dependencies"""
    service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
    service.msal_app = mock_msal_app
    return service


@pytest.mark.asyncio
async def test_generate_authorization_url(microsoft_service, mock_redis):
    """Test generating Microsoft OAuth authorization URL"""
    auth_url, state = await microsoft_service.generate_authorization_url()

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == f"oauth_state:{state}"
    assert call_args[0][1] == 600
    assert call_args[0][2] == "pending"

    assert "https://login.microsoftonline.com/" in auth_url
    assert "oauth2/v2.0/authorize" in auth_url
    assert f"state={state}" in auth_url
    assert "response_type=code" in auth_url
    assert "prompt=select_account" in auth_url


@pytest.mark.asyncio
async def test_validate_state_success(microsoft_service, mock_redis):
    """Test successful OAuth state validation"""
    test_state = "valid_state_123"
    mock_redis.get.return_value = "pending"

    result = await microsoft_service.validate_state(test_state)

    assert result is True
    mock_redis.get.assert_called_once_with(f"oauth_state:{test_state}")


@pytest.mark.asyncio
async def test_validate_state_failure(microsoft_service, mock_redis):
    """Test failed OAuth state validation"""
    test_state = "invalid_state_456"
    mock_redis.get.return_value = None

    result = await microsoft_service.validate_state(test_state)

    assert result is False
    mock_redis.get.assert_called_once_with(f"oauth_state:{test_state}")


@pytest.mark.asyncio
async def test_exchange_code_for_token_success(microsoft_service, mock_redis, mock_msal_app):
    """Test successful token exchange"""
    test_code = "auth_code_123"
    test_state = "state_456"
    mock_token_response = {
        "access_token": "ms_access_token_xyz",
        "refresh_token": "ms_refresh_token_abc",
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    mock_msal_app.acquire_token_by_authorization_code.return_value = mock_token_response

    result = await microsoft_service.exchange_code_for_token(test_code, test_state)

    assert result == mock_token_response
    assert "access_token" in result
    mock_redis.delete.assert_called_once_with(f"oauth_state:{test_state}")
    mock_msal_app.acquire_token_by_authorization_code.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_code_for_token_error(microsoft_service, mock_redis, mock_msal_app):
    """Test token exchange with error response"""
    test_code = "invalid_code"
    test_state = "state_789"
    mock_error_response = {
        "error": "invalid_grant",
        "error_description": "The authorization code is invalid or expired",
    }

    mock_msal_app.acquire_token_by_authorization_code.return_value = mock_error_response

    with pytest.raises(ValueError) as exc_info:
        await microsoft_service.exchange_code_for_token(test_code, test_state)

    assert "Failed to exchange code" in str(exc_info.value)
    assert "invalid or expired" in str(exc_info.value)
    mock_redis.delete.assert_called_once_with(f"oauth_state:{test_state}")


@pytest.mark.asyncio
async def test_get_user_info_uses_user_principal_name_fallback(microsoft_service):
    """Test user info falls back to userPrincipalName when mail is not available"""
    test_access_token = "ms_access_token_xyz"
    mock_user_data = {
        "id": "ms_user_456",
        "userPrincipalName": "user@tenant.onmicrosoft.com",
        "displayName": "Fallback User",
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        user_info = await microsoft_service.get_user_info(test_access_token)

    assert user_info.email == "user@tenant.onmicrosoft.com"


@pytest.mark.asyncio
async def test_get_user_info_api_error(microsoft_service):
    """Test handling of Microsoft Graph API errors"""
    test_access_token = "invalid_token"

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError) as exc_info:
            await microsoft_service.get_user_info(test_access_token)

    assert "Failed to fetch user information" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_user_info_http_error(microsoft_service):
    """Test handling of HTTP errors when fetching user info"""
    test_access_token = "ms_access_token_xyz"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=HTTPError("Connection failed")
        )

        with pytest.raises(ValueError) as exc_info:
            await microsoft_service.get_user_info(test_access_token)

    assert "Failed to communicate with Microsoft Graph API" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_or_create_user_existing_user(pg_sync_session, pg_async_session, mock_redis):
    """Test retrieving an existing user"""
    session = pg_sync_session

    existing_user = User(
        email="existing@example.com",
        hashed_password=hash_password("password123"),
        name="Existing User",
        is_verified=True,
        is_active=True,
        auth_provider="microsoft",
    )
    session.add(existing_user)
    session.commit()

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_123",
            email="existing@example.com",
            display_name="Existing User",
            given_name="Existing",
            surname="User",
            user_principal_name="existing@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is False
    assert user.email == "existing@example.com"
    assert user.auth_provider == "microsoft"


@pytest.mark.asyncio
async def test_get_or_create_user_converts_local_to_microsoft(
    pg_sync_session, pg_async_session, mock_redis
):
    """Test converting a local auth user to Microsoft auth"""
    session = pg_sync_session

    local_user = User(
        email="local@example.com",
        hashed_password=hash_password("password123"),
        name="Local User",
        is_verified=False,
        is_active=True,
        auth_provider="local",
    )
    session.add(local_user)
    session.commit()

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_456",
            email="local@example.com",
            display_name="Local User",
            given_name="Local",
            surname="User",
            user_principal_name="local@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is False
    assert user.email == "local@example.com"
    assert user.auth_provider == "microsoft"
    assert user.is_verified is True


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new_user(pg_sync_session, pg_async_session, mock_redis):
    """Test creating a new user from Microsoft OAuth"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_789",
            email="newuser@example.com",
            display_name="New User",
            given_name="New",
            surname="User",
            user_principal_name="newuser@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is True
    assert user.email == "newuser@example.com"

    assert user.name in ["New User", "newuser@example.com"]
    assert user.auth_provider == "microsoft"
    assert user.is_verified is True
    assert user.is_active is True
    assert user.hashed_password is not None


@pytest.mark.asyncio
async def test_get_or_create_user_uses_email_as_name_fallback(
    pg_sync_session, pg_async_session, mock_redis
):
    """Test using email as name when display_name is not available"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_999",
            email="noname@example.com",
            display_name=None,
            given_name=None,
            surname=None,
            user_principal_name="noname@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is True
    assert user.name == "noname@example.com"


@pytest.mark.asyncio
async def test_complete_oauth_flow_success(
    pg_sync_session, pg_async_session, mock_redis, mock_msal_app
):
    """Test complete OAuth flow with new user"""
    test_code = "auth_code_abc"
    test_state = "state_xyz"

    mock_redis.get.return_value = "pending"

    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "access_token": "ms_access_token_123",
        "refresh_token": "ms_refresh_token_456",
    }

    mock_user_data = {
        "id": "ms_user_complete",
        "mail": "complete@example.com",
        "displayName": "Complete User",
        "givenName": "Complete",
        "surname": "User",
        "userPrincipalName": "complete@example.com",
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with patch(
                "app.api.modules.v1.auth.service.oauth_microsoft.get_redis_client",
                return_value=mock_redis,
            ):
                result = await service.complete_oauth_flow(test_code, test_state)

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert result["email"] == "complete@example.com"
    assert result["is_new_user"] is True
    assert "user_id" in result


@pytest.mark.asyncio
async def test_complete_oauth_flow_invalid_state(microsoft_service, mock_redis):
    """Test complete OAuth flow fails with invalid state"""
    mock_redis.get.return_value = None

    with pytest.raises(ValueError) as exc_info:
        await microsoft_service.complete_oauth_flow("code", "invalid_state")

    assert "Invalid or expired state parameter" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_oauth_flow_no_access_token(pg_async_session, mock_redis, mock_msal_app):
    """Test complete OAuth flow fails when no access token in response"""
    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "refresh_token": "ms_refresh_token_only",
    }

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with pytest.raises(ValueError) as exc_info:
            await service.complete_oauth_flow("code", "state")

    assert "No access token in response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_oauth_flow_existing_user(
    pg_sync_session, pg_async_session, mock_redis, mock_msal_app
):
    """Test complete OAuth flow with existing user"""
    session = pg_sync_session

    existing_user = User(
        email="existing.flow@example.com",
        hashed_password=hash_password("password123"),
        name="Existing Flow User",
        is_verified=True,
        is_active=True,
        auth_provider="microsoft",
    )
    session.add(existing_user)
    session.commit()

    test_code = "auth_code_existing"
    test_state = "state_existing"

    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "access_token": "ms_access_token_existing",
    }

    mock_user_data = {
        "id": "ms_user_existing",
        "mail": "existing.flow@example.com",
        "displayName": "Existing Flow User",
        "userPrincipalName": "existing.flow@example.com",
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with patch(
                "app.api.modules.v1.auth.service.oauth_microsoft.get_redis_client",
                return_value=mock_redis,
            ):
                result = await service.complete_oauth_flow(test_code, test_state)

    assert result["email"] == "existing.flow@example.com"
    assert result["is_new_user"] is False
