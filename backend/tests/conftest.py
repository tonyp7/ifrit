import asyncio
import os
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models.file import FILE_TAGS_SEED_STATEMENT


def _test_database_url() -> str:
    # Deliberately not a Settings field (app.core.config): nothing about the
    # deployed app ever reads a test database URL, only this test suite does, a
    # test-only concept has no business living in the app's own runtime config.
    # Derived from `database_url` (e.g. .../ifrit -> .../ifrit_test) instead of a
    # separately configured value, so there's no second env var to set/forget and
    # no way for it to drift from whichever database the app itself is pointed
    # at. This *must* never resolve to the same database as `database_url`,
    # db_session below unconditionally drops every table on teardown, which would
    # be destructive against real dev/prod data (see the fixture's `drop_all`).
    url = make_url(settings.database_url)
    # Under pytest-xdist every worker gets a database of its own (ifrit_test_gw0, ...): the
    # workers run at the same time, and each one empties its database after every test.
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    suffix = f"_test_{worker}" if worker else "_test"
    test_url = url.set(database=f"{url.database}{suffix}")
    assert test_url.database != url.database
    # Not `str(test_url)`: SQLAlchemy's URL.__str__ deliberately masks the
    # password (renders it as literal "***") for safe printing/logging: passing
    # that straight to asyncpg/create_async_engine would try to authenticate with
    # the string "***" as the password, not the real one. render_as_string with
    # hide_password=False is the actual connection string.
    return test_url.render_as_string(hide_password=False)


async def _ensure_test_database_exists() -> None:
    url = make_url(_test_database_url())
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database="postgres",
    )
    try:
        await conn.execute(f'CREATE DATABASE "{url.database}"')
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


# Small enough that size-limit tests stay cheap, large enough for any test image.
TEST_MAX_UPLOAD_BYTES = 100_000


@pytest.fixture(autouse=True)
def _storage_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test stores files in its own temporary directory, never in the developer's
    real STORAGE_ROOT, with a small upload limit."""
    root = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", root)
    monkeypatch.setattr(settings, "max_upload_bytes", TEST_MAX_UPLOAD_BYTES)
    return root


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    # The limiter's counters are process-global and every test client shares one source
    # address, so without this the suite's many logins would trip the login limit and
    # tests would depend on run order.
    limiter.reset()


async def reset_database(conn: AsyncConnection) -> None:
    """Empties every table and puts back the rows `create_all` seeds, so the next test
    starts from the same state as a freshly built schema, for a fraction of the cost of
    dropping and creating every table again. Triggers and functions are schema objects
    and survive the truncate."""
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    # The one data row set an `after_create` hook inserts (the default file tags).
    await conn.execute(text(FILE_TAGS_SEED_STATEMENT))


async def _build_schema() -> None:
    engine = create_async_engine(_test_database_url())
    try:
        async with engine.begin() as conn:
            # Dropped first: a run that crashed halfway may have left tables behind.
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _drop_schema() -> None:
    engine = create_async_engine(_test_database_url())
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def _test_schema() -> Iterator[str | None]:
    """Builds the test schema once for the whole session (once per xdist worker), and
    yields why it could not, if it could not. Synchronous, with its own event loop and
    engine, so that nothing it opens is reused inside a test's loop (see db_session)."""
    try:
        asyncio.run(_ensure_test_database_exists())
        asyncio.run(_build_schema())
    except (SQLAlchemyError, OSError, asyncpg.PostgresError) as exc:  # pragma: no cover
        yield f"Postgres not reachable for integration tests: {exc}"
        return
    try:
        yield None
    finally:
        asyncio.run(_drop_schema())


@pytest_asyncio.fixture
async def db_session(_test_schema: str | None) -> AsyncGenerator[AsyncSession]:
    if _test_schema is not None:  # pragma: no cover - environment-dependent
        pytest.skip(_test_schema)
    # A fresh engine per test (rather than a module-level singleton): SQLAlchemy's
    # async engine binds its connection pool to the event loop active when it opens
    # its first connection, and pytest-asyncio gives each test its own loop: a
    # shared engine would break on the second test ("attached to a different loop").
    test_engine = create_async_engine(_test_database_url())
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    try:
        async with test_session_factory() as session:
            yield session
    finally:
        # After the session has closed, so its connection holds no lock the truncate
        # would wait on; in a `finally`, so a failing test still leaves a clean database.
        async with test_engine.begin() as conn:
            await reset_database(conn)
        await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
