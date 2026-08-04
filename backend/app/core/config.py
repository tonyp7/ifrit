from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ifrit:ifrit@localhost:5432/ifrit"
    # Separate database for the integration test suite — never the dev/app database,
    # so tests can freely create/drop schema without touching real dev data.
    test_database_url: str = "postgresql+asyncpg://ifrit:ifrit@localhost:5432/ifrit_test"

    jwt_secret_key: str = "dev-only-insecure-secret-key-change-me-3f8a1c9d"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = ["http://localhost:5173"]
    # Cookies must be Secure (HTTPS-only) in production; disabled by default for local
    # http:// dev. Set COOKIE_SECURE=true wherever the app is served over TLS.
    cookie_secure: bool = False

    seed_admin_email: str = "admin@ifrit.local"
    seed_admin_password: str = "changeme123"


settings = Settings()
