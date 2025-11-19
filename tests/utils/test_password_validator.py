import pytest
from app.api.utils.validators import is_strong_password


def test_is_strong_password_all_missing():
    password = "abc"
    error = is_strong_password(password)
    assert "at least 8 characters" in error
    assert "one uppercase letter" in error
    assert "one digit" in error
    assert "one special character" in error


def test_is_strong_password_some_missing():
    password = "abcdefgh"
    error = is_strong_password(password)
    assert "one uppercase letter" in error
    assert "one digit" in error
    assert "one special character" in error


def test_is_strong_password_valid():
    password = "Abcdef1!"
    error = is_strong_password(password)
    assert error == ""
