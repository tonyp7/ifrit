import pytest
from pydantic import ValidationError

from app.core.config import Settings

_REQUIRED = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
    "JWT_SECRET_KEY": "k",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "15",
    "REFRESH_TOKEN_EXPIRE_MINUTES": "60",
    "CORS_ORIGINS": '["http://localhost"]',
    "SEED_ADMIN_EMAIL": "a@example.com",
    "SEED_ADMIN_PASSWORD": "x",
    "STORAGE_ROOT": "/tmp/ifrit-test-storage",
    "MAX_UPLOAD_BYTES": "1024",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> Settings:
    for key, value in {**_REQUIRED, **overrides}.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    # _env_file=None: only the environment set above counts, not the developer's .env.
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_storage_settings_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _settings(monkeypatch)
    assert str(settings.storage_root) == "/tmp/ifrit-test-storage"
    assert settings.max_upload_bytes == 1024


@pytest.mark.parametrize("missing", ["STORAGE_ROOT", "MAX_UPLOAD_BYTES"])
def test_missing_storage_setting_refuses_to_start(
    monkeypatch: pytest.MonkeyPatch, missing: str
):
    with pytest.raises(ValidationError) as excinfo:
        _settings(monkeypatch, **{missing: None})
    assert missing.lower() in str(excinfo.value)
