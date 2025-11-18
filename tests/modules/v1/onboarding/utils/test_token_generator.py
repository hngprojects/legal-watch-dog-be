import pytest

from app.api.modules.v1.onboarding.utils import token_generator


def test_make_token_unique_and_length():
    t1 = token_generator.make_token()
    t2 = token_generator.make_token()
    assert isinstance(t1, str)
    assert isinstance(t2, str)
    assert t1 != t2
    assert len(t1) >= 43  # token_urlsafe(32) yields >=43 characters typically


def test_hash_and_verify_token():
    token = token_generator.make_token()
    hashed = token_generator.hash_token(token)
    assert isinstance(hashed, str)
    # hashed should not equal raw token
    assert hashed != token
    assert token_generator.verify_token(token, hashed) is True
    assert token_generator.verify_token("wrongtoken", hashed) is False
