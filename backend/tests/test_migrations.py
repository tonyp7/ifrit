"""The Alembic migration, run for real.

Every other test builds its schema from the models (`Base.metadata.create_all`), so the
migration that actually creates production databases is never exercised by them. This one
runs it on an empty scratch database and requires that it agrees with the models.

It is a plain (synchronous) test on purpose: Alembic's env.py drives the migration with
`asyncio.run`, which cannot be called from inside the event loop of an async test.
"""

import asyncio
import importlib.util
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy import CheckConstraint, Table
from sqlalchemy.engine import URL, make_url

from alembic import command
from app.core.config import settings
from app.models.invoice import Invoice, InvoiceLine, InvoiceReference
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
    assert {row["name"] for row in roles} == {"administrator", "manager", "consultant", "billing"}
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
    assert {"app_settings", "billing_milestones", "project_references"} <= _tables()

    command.downgrade(scratch_database, "0005")
    assert "issued_at" not in _columns("invoices")

    numbering = {"invoice_numbering_formats", "invoice_number_counters"}
    assert numbering <= _tables()
    command.downgrade(scratch_database, "0004")
    assert not numbering & _tables()
    assert "invoices" in _tables()

    command.downgrade(scratch_database, "0003")
    assert not {"invoices", "invoice_lines", "invoice_references"} & _tables()

    command.downgrade(scratch_database, "0002")
    roles = asyncio.run(_fetch("SELECT name FROM roles"))
    assert "billing" not in {row["name"] for row in roles}

    command.downgrade(scratch_database, "0001")
    assert not {"billing_milestones", "project_references"} & _tables()
    assert "app_settings" in _tables()

    command.downgrade(scratch_database, "base")
    assert _tables() == {"alembic_version"}

    command.upgrade(scratch_database, "head")
    assert {"app_settings", "billing_milestones", "project_references"} <= _tables()


# Users seeded on 0001 to check how 0002 folds the two project roles into `manager`.
_PA_ONLY = "10000000-0000-0000-0000-000000000001"
_PM_ONLY = "10000000-0000-0000-0000-000000000002"
_BOTH = "10000000-0000-0000-0000-000000000003"
_PROJECT = "20000000-0000-0000-0000-000000000001"
_ADMIN_ROLE = "00000000-0000-0000-0000-000000000001"
_PROJECT_ADMIN_ROLE = "00000000-0000-0000-0000-000000000002"
_CONSULTANT_ROLE = "00000000-0000-0000-0000-000000000003"
_PROJECT_MANAGER_ROLE = "00000000-0000-0000-0000-000000000004"


async def _execute(*statements: str) -> None:
    url = SCRATCH_URL
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database=url.database,
    )
    try:
        for statement in statements:
            await conn.execute(statement)
    finally:
        await conn.close()


def _roles_by_user() -> dict[str, set[str]]:
    rows = asyncio.run(
        _fetch(
            "SELECT ur.user_id::text AS user_id, r.name FROM user_roles ur "
            "JOIN roles r ON r.id = ur.role_id"
        )
    )
    out: dict[str, set[str]] = {}
    for row in rows:
        out.setdefault(row["user_id"], set()).add(row["name"])
    return out


def test_the_role_merge_folds_both_project_roles_into_manager(scratch_database) -> None:
    command.upgrade(scratch_database, "0001")
    asyncio.run(
        _execute(
            f"""INSERT INTO users (id, name_id, full_name) VALUES
                ('{_PA_ONLY}', 'pa@example.com', 'PA'),
                ('{_PM_ONLY}', 'pm@example.com', 'PM'),
                ('{_BOTH}', 'both@example.com', 'Both')""",
            f"""INSERT INTO user_roles (user_id, role_id) VALUES
                ('{_PA_ONLY}', '{_PROJECT_ADMIN_ROLE}'),
                ('{_PA_ONLY}', '{_CONSULTANT_ROLE}'),
                ('{_PM_ONLY}', '{_PROJECT_MANAGER_ROLE}'),
                ('{_BOTH}', '{_PROJECT_ADMIN_ROLE}'),
                ('{_BOTH}', '{_PROJECT_MANAGER_ROLE}'),
                ('{_BOTH}', '{_ADMIN_ROLE}')""",
            f"""INSERT INTO projects (id, name, invoicing_currency, project_type)
                VALUES ('{_PROJECT}', 'P', 'EUR', 'time_and_material')""",
            f"""INSERT INTO project_managers (project_id, user_id) VALUES
                ('{_PROJECT}', '{_PM_ONLY}'), ('{_PROJECT}', '{_BOTH}')""",
        )
    )

    command.upgrade(scratch_database, "0002")

    assert _roles_by_user() == {
        _PA_ONLY: {"manager", "consultant"},
        _PM_ONLY: {"manager"},
        _BOTH: {"manager", "administrator"},
    }
    (count,) = asyncio.run(_fetch("SELECT count(*) AS n FROM user_roles"))
    assert count["n"] == 5  # one manager row each, nothing duplicated
    managers = asyncio.run(_fetch("SELECT user_id::text AS user_id FROM project_managers"))
    assert {row["user_id"] for row in managers} == {_PM_ONLY, _BOTH}

    # The downgrade can't tell who held which role, so every manager gets both back.
    command.downgrade(scratch_database, "0001")

    assert _roles_by_user() == {
        _PA_ONLY: {"project_admin", "project_manager", "consultant"},
        _PM_ONLY: {"project_admin", "project_manager"},
        _BOTH: {"project_admin", "project_manager", "administrator"},
    }


def _model_checks(model: type) -> dict[str, str]:
    table = model.__table__
    assert isinstance(table, Table)
    return {
        c.name: str(c.sqltext)
        for c in table.constraints
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }


def test_the_invoice_checks_match_the_models() -> None:
    # `alembic check` compares columns, indexes and foreign keys but not CHECK constraints,
    # so the invoice tables' vocabularies and all-or-nothing rules are compared here.
    path = BACKEND_DIR / "alembic" / "versions" / "0004_invoices.py"
    spec = importlib.util.spec_from_file_location("migration_0004", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    issue_path = BACKEND_DIR / "alembic" / "versions" / "0006_invoice_issue_void.py"
    issue_spec = importlib.util.spec_from_file_location("migration_0006", issue_path)
    assert issue_spec is not None and issue_spec.loader is not None
    issue = importlib.util.module_from_spec(issue_spec)
    issue_spec.loader.exec_module(issue)

    assert {
        **module._INVOICE_CHECKS,
        "ck_invoices_issued_fields": issue._ISSUED_FIELDS_CHECK,
        "ck_invoices_void_fields": issue._VOID_FIELDS_CHECK,
    } == _model_checks(Invoice)
    assert module._LINE_CHECKS == _model_checks(InvoiceLine)
    assert module._REFERENCE_CHECKS == _model_checks(InvoiceReference)


def test_an_invoice_does_not_depend_on_payee_accounts(scratch_database) -> None:
    command.upgrade(scratch_database, "head")

    rows = asyncio.run(
        _fetch(
            "SELECT confrelid::regclass::text AS target FROM pg_constraint "
            "WHERE conrelid = 'invoices'::regclass AND contype = 'f'"
        )
    )
    assert {row["target"] for row in rows} == {"projects", "currencies", "users"}


def _columns(table: str) -> set[str]:
    rows = asyncio.run(
        _fetch(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = '{table}'"
        )
    )
    return {row["column_name"] for row in rows}


def test_downgrading_below_issuing_is_refused_once_an_invoice_is_issued(
    scratch_database,
) -> None:
    command.upgrade(scratch_database, "head")
    asyncio.run(
        _fetch(
            """
            WITH c AS (
                INSERT INTO companies (id, legal_name, country_of_registration, is_vendor)
                VALUES (gen_random_uuid(), 'C', 'BE', true) RETURNING id
            ), p AS (
                INSERT INTO projects (id, name, vendor_company_id, client_company_id,
                    invoicing_currency, project_type, status)
                SELECT gen_random_uuid(), 'P', c.id, c.id, 'EUR', 'time_and_material', 'active'
                FROM c RETURNING id
            )
            INSERT INTO invoices (id, status, number, project_id, currency_code,
                bill_from_name, bill_to_name, subtotal, total, invoice_date, issued_at,
                currency_minor_unit)
            SELECT gen_random_uuid(), 'issued', 'INV-1', p.id, 'EUR', 'F', 'T', 0, 0,
                current_date, now(), 2
            FROM p RETURNING id
            """
        )
    )

    with pytest.raises(RuntimeError, match="issued or void"):
        command.downgrade(scratch_database, "0005")
    assert "issued_at" in _columns("invoices")
