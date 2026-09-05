import uuid

from pydantic import BaseModel, Field, model_validator

from app.models.user import ThemePreference

# See docs/requirements/user.md#password-policy.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 255
VALID_ROLES = {"administrator", "project_admin", "project_manager", "consultant"}


def _check_password_value(password: str) -> None:
    if not password.isprintable():
        # str.isprintable() rejects Unicode control/format/separator characters
        # while still treating the ASCII space as printable (Python's own carve-out)
        # — exactly this policy's "all printable characters, including spaces and
        # Unicode/emoji" rule.
        raise ValueError("Password must only contain printable characters")


class UserOut(BaseModel):
    id: uuid.UUID
    name_id: str
    full_name: str
    roles: list[str]
    is_sso: bool
    is_active: bool
    theme_preference: ThemePreference


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class UserCreate(BaseModel):
    full_name: str
    name_id: str
    is_sso: bool = False
    roles: list[str] = Field(min_length=1)
    password: str | None = Field(
        default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )

    @model_validator(mode="after")
    def check_fields(self) -> "UserCreate":
        if not self.full_name.strip():
            raise ValueError("full_name must not be empty")
        if not self.name_id.strip():
            raise ValueError("name_id must not be empty")
        if not set(self.roles).issubset(VALID_ROLES):
            raise ValueError(f"roles must be a subset of {sorted(VALID_ROLES)}")
        if self.password is not None:
            _check_password_value(self.password)
        # See docs/requirements/user.md#user-form-create--edit--duplicate: a local
        # user needs an initial password; an SSO user must never have one set.
        if not self.is_sso and not self.password:
            raise ValueError("password is required for a local (non-SSO) user")
        if self.is_sso and self.password is not None:
            raise ValueError("password must not be set for an SSO user")
        return self


class UserUpdate(BaseModel):
    full_name: str
    name_id: str
    is_sso: bool
    roles: list[str] = Field(min_length=1)
    # Whether a password is required/allowed here depends on the transition
    # relative to the user's CURRENT is_sso — not derivable from this payload alone
    # (e.g. staying local doesn't require one; switching SSO -> local does) — see
    # update_user in app/services/user_service.py, which enforces this with the
    # prior state in hand, not this schema.
    password: str | None = Field(
        default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )

    @model_validator(mode="after")
    def check_fields(self) -> "UserUpdate":
        if not self.full_name.strip():
            raise ValueError("full_name must not be empty")
        if not self.name_id.strip():
            raise ValueError("name_id must not be empty")
        if not set(self.roles).issubset(VALID_ROLES):
            raise ValueError(f"roles must be a subset of {sorted(VALID_ROLES)}")
        if self.password is not None:
            _check_password_value(self.password)
        return self


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @model_validator(mode="after")
    def check_password(self) -> "PasswordResetRequest":
        _check_password_value(self.new_password)
        return self


class ThemePreferenceUpdate(BaseModel):
    theme_preference: ThemePreference
