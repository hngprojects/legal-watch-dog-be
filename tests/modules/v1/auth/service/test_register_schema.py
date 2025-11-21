"""Tests for register schema validation."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.api.modules.v1.auth.schemas.register import RegisterRequest
from app.api.utils.email_verifier import BusinessEmailVerifier


def test_register_rejects_free_provider():
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    # Ensure test providers are not allowed
    with patch("app.api.modules.v1.auth.service.validators.settings") as mock_settings:
        mock_settings.ALLOW_TEST_EMAIL_PROVIDERS = False
        mock_settings.TEST_EMAIL_PROVIDERS = "gmail.com"

        with pytest.raises(ValidationError):
            RegisterRequest(
                name="Acme",
                email="someone@gmail.com",
                password="Password1!",
                confirm_password="Password1!",
                industry="Legal",
            )


def test_register_allows_business_email():
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    model = RegisterRequest(
        name="Acme",
        email="someone@company.com",
        password="Password1!",
        confirm_password="Password1!",
        industry="Legal",
    )

    assert model.email == "someone@company.com"


def test_register_allows_role_based_email():
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    model = RegisterRequest(
        name="Acme",
        email="admin@company.com",
        password="Password1!",
        confirm_password="Password1!",
        industry="Legal",
    )

    assert model.email == "admin@company.com"
