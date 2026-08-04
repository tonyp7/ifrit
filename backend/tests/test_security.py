import uuid

import pytest

from app.auth.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, roles=["administrator"])
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == str(user_id)
    assert payload["roles"] == ["administrator"]


def test_refresh_token_rejected_as_access() -> None:
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id)
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="access")
