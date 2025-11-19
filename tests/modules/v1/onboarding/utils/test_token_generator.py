import pytest
from app.api.modules.v1.onboarding.utils.token_generator import (
    make_token,
    hash_token,
    verify_token,
)


def test_make_token():
    token = make_token()
    assert isinstance(token, str)
    assert len(token) > 0


def test_hash_token():
    token = "test_token"
    hashed = hash_token(token)
    assert isinstance(hashed, str)
    assert len(hashed) == 64  # SHA256 produces a 64-character hex digest


def test_verify_token():
    token = "test_token"
    hashed = hash_token(token)
    assert verify_token(token, hashed)
    assert not verify_token("wrong_token", hashed)
