from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import Base, get_db
from app.core.rate_limit import limiter
from app.main import app


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
    test_url = url.set(database=f"{url.database}_test")
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
        host=url.host, port=url.port, user=url.username, password=url.password,
        database="postgres",
    )
    try:
        await conn.execute(f'CREATE DATABASE "{url.database}"')
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    # The limiter's counters are process-global and every test client shares one source
    # address, so without this the suite's many logins would trip the login limit and
    # tests would depend on run order.
    limiter.reset()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # A fresh engine per test (rather than a module-level singleton): SQLAlchemy's
    # async engine binds its connection pool to the event loop active when it opens
    # its first connection, and pytest-asyncio gives each test its own loop: a
    # shared engine would break on the second test ("attached to a different loop").
    test_engine = create_async_engine(_test_database_url())
    try:
        await _ensure_test_database_exists()
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:  # pragma: no cover - environment-dependent
        await test_engine.dispose()
        pytest.skip(f"Postgres not reachable for integration tests: {exc}")

    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    try:
        async with test_session_factory() as session:
            yield session
    finally:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
