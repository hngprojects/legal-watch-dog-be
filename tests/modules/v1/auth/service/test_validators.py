import pytest

from app.api.modules.v1.auth.service.validators import (
    is_company_email,
    is_strong_password,
)


@pytest.mark.parametrize(
    "email,expected",
    [
        ("user@company.com", True),
        ("user@gmail.com", True),
        ("user@yahoo.com", False),
        ("employee@enterprise.org", True),
        ("admin@outlook.com", False),
    ],
)
def test_is_company_email(email, expected):
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
