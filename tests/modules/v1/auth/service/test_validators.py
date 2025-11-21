"""Tests for validators."""

from unittest.mock import patch

import pytest

from app.api.modules.v1.auth.service.validators import (
    is_company_email,
    is_strong_password,
)


@pytest.mark.parametrize(
    "email,expected",
    [
        ("user@company.com", True),
        ("user@gmail.com", False),
        ("user@yahoo.com", False),
        (
            "admin@company.com",
            True,
        ),
        ("someone@mailinator.com", False),
        ("employee@enterprise.org", True),
        ("admin@outlook.com", False),
    ],
)
def test_is_company_email(email, expected):
    from app.api.utils.email_verifier import BusinessEmailVerifier

    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    # Ensure test providers are not allowed
    with patch("app.api.modules.v1.auth.service.validators.settings") as mock_settings:
        mock_settings.ALLOW_TEST_EMAIL_PROVIDERS = False
        mock_settings.TEST_EMAIL_PROVIDERS = "gmail.com"

        assert is_company_email(email) == expected


@pytest.mark.parametrize(
    "password,expected",
    [
        ("Password1!", True),
        ("password", False),
        ("PASSWORD1!", False),
        ("Password!", False),
        ("Password1", False),
        ("Pass1!", False),
        ("StrongPass123$", True),
    ],
)
def test_is_strong_password(password, expected):
    assert is_strong_password(password) == expected
