from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # No default — every field below must come from .env/the real environment, not
    # a value baked into source. For the secrets (jwt_secret_key,
    # seed_admin_password) this is a real security fix: a hardcoded fallback there
    # would mean a deployment that forgets to set the env var silently runs with a
    # value published in this repo's own .env.example, rather than failing to
    # start (see specs/sast.md). For the rest it's for consistency — no field
    # should look configurable via .env while actually tolerating being unset.
    # Local dev is unaffected: .env already sets all of these explicitly.
    #
    # No test_database_url here, deliberately: nothing about the deployed app
    # ever reads a test database URL, only the test suite does — see
    # tests/conftest.py's _test_database_url(), which derives it from
    # database_url instead of needing a config field of its own.
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_minutes: int

    cors_origins: list[str]
    # Cookies must be Secure (HTTPS-only) in production; disabled by default for local
    # http:// dev. Set COOKIE_SECURE=true wherever the app is served over TLS.
    cookie_secure: bool = False

    seed_admin_email: str
    seed_admin_password: str


settings = Settings()
