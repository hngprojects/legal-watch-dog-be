from unittest.mock import AsyncMock, patch

import pytest

from app.api.utils.organization_validations import (
    validate_no_pending_registration,
    validate_organization_email_available,
)


@pytest.mark.asyncio
async def test_validate_organization_email_available_passes():
    """Passes when email is not registered"""
    db_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_organization_by_email",
        new=AsyncMock(return_value=None),
    ):
        await validate_organization_email_available(db_mock, "test@example.com")


@pytest.mark.asyncio
async def test_validate_organization_email_available_fails():
    """Raises ValueError when email is already registered"""
    db_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_organization_by_email",
        new=AsyncMock(return_value={"id": 1}),
    ):
        with pytest.raises(ValueError) as exc:
            await validate_organization_email_available(db_mock, "test@example.com")
        assert str(exc.value) == "An organization with this email already exists."


@pytest.mark.asyncio
async def test_validate_no_pending_registration_passes():
    """Passes when no pending registration exists"""
    redis_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_organization_credentials",
        new=AsyncMock(return_value=None),
    ):
        await validate_no_pending_registration(redis_mock, "test@example.com")


@pytest.mark.asyncio
async def test_validate_no_pending_registration_fails():
    """Raises ValueError when pending registration exists"""
    redis_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_organization_credentials",
        new=AsyncMock(return_value={"otp_code": "123456"}),
    ):
        with pytest.raises(ValueError) as exc:
            await validate_no_pending_registration(redis_mock, "test@example.com")
        assert str(exc.value) == (
            "A registration with this email is already pending OTP verification."
        )
