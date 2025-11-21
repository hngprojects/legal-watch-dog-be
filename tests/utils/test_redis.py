import json
from unittest.mock import AsyncMock

import pytest

from app.api.utils.redis import (
    delete_organization_credentials,
    get_organization_credentials,
    store_organization_credentials,
    verify_and_get_credentials,
)


@pytest.mark.asyncio
async def test_store_organization_credentials_success():
    """Test storing organization credentials in Redis successfully."""
    redis_mock = AsyncMock()
    registration_data = {
        "name": "Test Org",
        "email": "test@example.com",
        "industry": "Tech",
        "hashed_password": "hashed_pw",
        "otp_code": "123456",
    }

    result = await store_organization_credentials(
        redis_mock, "test@example.com", registration_data, ttl_seconds=300
    )

    redis_mock.setex.assert_awaited_once_with(
        name="pending_registration:test@example.com", time=300, value=json.dumps(registration_data)
    )
    assert result is True


@pytest.mark.asyncio
async def test_get_organization_credentials_exists():
    """Test retrieving existing organization credentials from Redis."""
    redis_mock = AsyncMock()
    registration_data = {
        "name": "Test Org",
        "email": "test@example.com",
        "industry": "Tech",
        "hashed_password": "hashed_pw",
        "otp_code": "123456",
    }
    redis_mock.get.return_value = json.dumps(registration_data)

    result = await get_organization_credentials(redis_mock, "test@example.com")

    redis_mock.get.assert_awaited_once_with("pending_registration:test@example.com")
    assert result == registration_data


@pytest.mark.asyncio
async def test_get_organization_credentials_not_exists():
    """Test retrieving non-existing organization credentials from Redis."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    result = await get_organization_credentials(redis_mock, "test@example.com")
    assert result is None


@pytest.mark.asyncio
async def test_delete_organization_credentials_success():
    """Test deleting existing organization credentials from Redis."""
    redis_mock = AsyncMock()
    redis_mock.delete.return_value = 1

    result = await delete_organization_credentials(redis_mock, "test@example.com")
    redis_mock.delete.assert_awaited_once_with("pending_registration:test@example.com")
    assert result is True


@pytest.mark.asyncio
async def test_delete_organization_credentials_not_exists():
    """Test deleting non-existing organization credentials from Redis."""
    redis_mock = AsyncMock()
    redis_mock.delete.return_value = 0

    result = await delete_organization_credentials(redis_mock, "test@example.com")
    assert result is False


@pytest.mark.asyncio
async def test_verify_and_get_credentials_success():
    """Test verifying OTP and retrieving credentials successfully."""
    redis_mock = AsyncMock()
    registration_data = {
        "name": "Test Org",
        "email": "test@example.com",
        "industry": "Tech",
        "hashed_password": "hashed_pw",
        "otp_code": "123456",
    }
    redis_mock.get.return_value = json.dumps(registration_data)

    result = await verify_and_get_credentials(redis_mock, "test@example.com", "123456")
    assert result == registration_data


@pytest.mark.asyncio
async def test_verify_and_get_credentials_invalid_otp():
    """Test verifying OTP with invalid code."""
    redis_mock = AsyncMock()
    registration_data = {
        "name": "Test Org",
        "email": "test@example.com",
        "industry": "Tech",
        "hashed_password": "hashed_pw",
        "otp_code": "123456",
    }
    redis_mock.get.return_value = json.dumps(registration_data)

    result = await verify_and_get_credentials(redis_mock, "test@example.com", "000000")
    assert result is None


@pytest.mark.asyncio
async def test_verify_and_get_credentials_no_data():
    """Test verifying OTP when no registration data exists."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    result = await verify_and_get_credentials(redis_mock, "test@example.com", "123456")
    assert result is None
