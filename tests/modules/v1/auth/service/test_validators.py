import pytest
from app.api.utils.validators import is_company_email
from app.api.modules.v1.auth.service.validators import is_strong_password


@pytest.mark.parametrize(
    "email,expected",
    [
        ("user@company.com", True),
        ("user@gmail.com", False),
        ("user@yahoo.com", False),
        (
            "admin@company.com",
            True,
        ),  # role-based local part, but allowed for company domains
        ("someone@mailinator.com", False),  # disposable
        ("employee@enterprise.org", True),
        ("admin@outlook.com", False),
    ],
)
def test_is_company_email(email, expected):
    # The verifier may attempt DNS lookups under the hood; patch MX resolution
    from app.api.utils.email_verifier import BusinessEmailVerifier

    # Always pretend MX records exist for deterministic tests
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True
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
