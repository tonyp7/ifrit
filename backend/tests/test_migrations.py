"""The Alembic migration, run for real.

Every other test builds its schema from the models (`Base.metadata.create_all`), so the
migration that actually creates production databases is never exercised by them. This one
runs it on an empty scratch database and requires that it agrees with the models.

It is a plain (synchronous) test on purpose: Alembic's env.py drives the migration with
`asyncio.run`, which cannot be called from inside the event loop of an async test.
"""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import URL, make_url

from alembic import command
from app.core.config import settings
from tests.conftest import _test_database_url

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _make_scratch_url() -> URL:
    """A database next to the test database, used only by this module and always dropped."""
    test_url = make_url(_test_database_url())
    return test_url.set(database=f"{test_url.database}_migrations")


# Worked out once, at import: the test database URL is derived from settings.database_url,
# which the fixture below points at this very database.
SCRATCH_URL = _make_scratch_url()


async def _admin(sql: str) -> None:
    """Runs one statement on the server's maintenance database (CREATE/DROP DATABASE)."""
    url = SCRATCH_URL
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _fetch(query: str) -> list[asyncpg.Record]:
    url = SCRATCH_URL
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database=url.database,
    )
    try:
        return list(await conn.fetch(query))
    finally:
        await conn.close()


@pytest.fixture
def scratch_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    """An empty database that Alembic is pointed at, and the Alembic config to drive it."""
    name = SCRATCH_URL.database
    try:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        asyncio.run(_admin(f'CREATE DATABASE "{name}"'))
    except (
        asyncpg.PostgresError,
        OSError,
    ) as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Postgres not reachable for the migration test: {exc}")

    # env.py takes its URL from the settings object, whatever the config says.
    monkeypatch.setattr(
        settings, "database_url", SCRATCH_URL.render_as_string(hide_password=False)
    )
    # No ini file: env.py would otherwise reconfigure logging for the rest of the session.
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    try:
        yield config
    finally:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def _tables() -> set[str]:
    rows = asyncio.run(
        _fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
    )
    return {row["table_name"] for row in rows}


def test_the_migration_builds_a_schema_that_matches_the_models(
    scratch_database,
) -> None:
    command.upgrade(scratch_database, "head")

    # Raises CommandError, listing every difference, if the models and the migration drift.
    command.check(scratch_database)


def test_the_migration_seeds_its_reference_data(scratch_database) -> None:
    command.upgrade(scratch_database, "head")

    roles = asyncio.run(_fetch("SELECT name FROM roles"))
    assert {row["name"] for row in roles} == {
        "administrator",
        "project_admin",
        "project_manager",
        "consultant",
    }
    (currencies,) = asyncio.run(
        _fetch(
            "SELECT count(*) AS total, count(*) FILTER (WHERE is_enabled) AS enabled "
            "FROM currencies"
        )
    )
    assert currencies["total"] > 0
    assert currencies["enabled"] > 0
    (tags,) = asyncio.run(_fetch("SELECT count(*) AS total FROM file_tags"))
    assert tags["total"] > 0
    settings_rows = asyncio.run(
        _fetch(
            "SELECT key, value::text AS value FROM app_settings "
            "WHERE group_name = 'pdf-export'"
        )
    )
    assert {row["key"]: row["value"] for row in settings_rows} == {
        "export_logo": "true",
        "logo_height_mm": "20",
    }


def test_the_migration_can_be_undone_and_applied_again(scratch_database) -> None:
    command.upgrade(scratch_database, "head")
    assert "app_settings" in _tables()

    command.downgrade(scratch_database, "base")
    assert _tables() == {"alembic_version"}

    command.upgrade(scratch_database, "head")
    assert "app_settings" in _tables()
