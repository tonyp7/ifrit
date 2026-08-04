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
from app.main import app


async def _ensure_test_database_exists() -> None:
    url = make_url(settings.test_database_url)
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


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # A fresh engine per test (rather than a module-level singleton): SQLAlchemy's
    # async engine binds its connection pool to the event loop active when it opens
    # its first connection, and pytest-asyncio gives each test its own loop — a
    # shared engine would break on the second test ("attached to a different loop").
    test_engine = create_async_engine(settings.test_database_url)
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
