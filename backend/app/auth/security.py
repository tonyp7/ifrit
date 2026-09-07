import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

# Argon2id, not bcrypt: bcrypt only uses the first 72 *bytes* of input, which the
# password policy's 255-character/full-Unicode allowance can easily exceed (see
# specs/requirements/user.md#password-policy) — Argon2 has no such practical limit.
_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, password)
    except VerifyMismatchError:
        return False


def _create_token(
    subject: uuid.UUID, token_type: Literal["access", "refresh"], expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: uuid.UUID, roles: list[str]) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        extra_claims={"roles": roles},
    )


def create_refresh_token(subject: uuid.UUID) -> str:
    return _create_token(
        subject, "refresh", timedelta(minutes=settings.refresh_token_expire_minutes)
    )


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as err:
        raise InvalidTokenError("Invalid or expired token") from err

    if payload.get("type") != expected_type:
        raise InvalidTokenError("Unexpected token type")

    return payload
