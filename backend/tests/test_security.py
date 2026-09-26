import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.auth.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import Settings, settings


def _claims(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": "ifrit",
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def _encode(claims: dict[str, object], algorithm: str | None = None) -> str:
    return jwt.encode(
        claims, settings.jwt_secret_key, algorithm=algorithm or settings.jwt_algorithm
    )


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, roles=["administrator"], token_version=3)
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == str(user_id)
    assert payload["roles"] == ["administrator"]
    assert payload["tv"] == 3


def test_refresh_token_rejected_as_access() -> None:
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id, token_version=0)
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="access")


def test_issued_tokens_carry_issuer() -> None:
    token = create_access_token(uuid.uuid4(), roles=[], token_version=0)
    assert decode_token(token, expected_type="access")["iss"] == "ifrit"


def test_hand_built_valid_claims_decode() -> None:
    # Guards the helpers below: the negative cases must fail for their one mutation only.
    assert decode_token(_encode(_claims()), expected_type="access")["type"] == "access"


def test_token_with_wrong_issuer_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token(_encode(_claims(iss="someone-else")), expected_type="access")


def test_token_without_issuer_rejected() -> None:
    # What every token issued before the issuer claim was introduced looks like.
    with pytest.raises(InvalidTokenError):
        decode_token(_encode(_claims(iss=None)), expected_type="access")


@pytest.mark.parametrize("claim", ["exp", "iat", "sub", "type"])
def test_token_missing_required_claim_rejected(claim: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_token(_encode(_claims(**{claim: None})), expected_type="access")


def test_token_signed_with_other_algorithm_rejected() -> None:
    other = "HS512" if settings.jwt_algorithm != "HS512" else "HS256"
    with pytest.raises(InvalidTokenError):
        decode_token(_encode(_claims(), algorithm=other), expected_type="access")


@pytest.mark.parametrize("algorithm", ["RS256", "ES256", "none", "hs256"])
def test_settings_reject_unsupported_jwt_algorithm(algorithm: str) -> None:
    valid = settings.model_dump()
    with pytest.raises(ValidationError):
        Settings(**{**valid, "jwt_algorithm": algorithm})
