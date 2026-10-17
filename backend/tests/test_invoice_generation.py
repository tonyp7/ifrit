from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.time_entry import TimeEntry
from tests.invoice_helpers import (
    add_service_line,
    log_hours,
    login,
    make_consultant,
    make_project,
)

URL = "/api/invoices/generate"
SEPTEMBER = {"period_start": "2026-09-01", "period_end": "2026-09-30"}


def _body(project, *lines, **overrides) -> dict:
    return {
        "project_id": str(project.id),
        "service_line_ids": [str(line.id) for line in lines],
        **SEPTEMBER,
        **overrides,
    }


async def test_hours_line_sums_locked_and_unlocked_entries(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)
    consultant = await make_consultant(db_session)
    # 152.5 hours over seven days, some locked and some not: 6 x 24 + 8.5.
    for day in range(1, 7):
        await log_hours(
            db_session, consultant, line, date(2026, 9, day), 24, locked=day % 2 == 0
        )
    await log_hours(db_session, consultant, line, date(2026, 9, 7), 8.5)
    # Outside the period: not counted.
    await log_hours(db_session, consultant, line, date(2026, 10, 1), 8)

    response = await client.post(URL, json=_body(project, line))

    assert response.status_code == 200
    body = response.json()
    [generated] = body["lines"]
    assert generated["name"] == "Senior developer"
    assert generated["uom"] == "hours"
    assert Decimal(generated["quantity"]) == Decimal("152.5")
    assert Decimal(generated["unit_price"]) == Decimal(95)
    assert body["omitted"] == []


async def test_days_use_the_standard_workday(client, db_session) -> None:
    await login(client, db_session, "administrator")
    project = await make_project(db_session)
    line = await add_service_line(db_session, project, name="Architect", uom="days")
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 1), 12)
    await log_hours(db_session, consultant, line, date(2026, 9, 2), 8)
    # Billing, not administrator, generates: log in again after the setting.
    await client.post("/api/auth/logout")
    await login(client, db_session)

    body = (await client.post(URL, json=_body(project, line))).json()

    assert Decimal(body["lines"][0]["quantity"]) == Decimal("2.5")


async def test_days_are_rounded_to_five_decimals(client, db_session) -> None:
    await login(client, db_session, "administrator")
    response = await client.patch(
        "/api/settings/general", json={"standard_workday_seconds": 7 * 3600}
    )
    assert response.status_code == 200
    await client.post("/api/auth/logout")
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project, uom="days", unit_price="700")
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 3), 10)

    body = (await client.post(URL, json=_body(project, line))).json()

    assert Decimal(body["lines"][0]["quantity"]) == Decimal("1.42857")


async def test_each_line_comes_out_empty_with_a_warning(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project, name="Licence", uom="ea")

    body = (await client.post(URL, json=_body(project, line))).json()

    assert [(item["name"], Decimal(item["quantity"])) for item in body["lines"]] == [
        ("Licence", Decimal(0))
    ]
    assert {"code": "zero_quantity", "service_lines": [], "companies": []} in body[
        "warnings"
    ]


async def test_lines_without_hours_are_left_out(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    busy = await add_service_line(db_session, project, name="Busy")
    idle = await add_service_line(db_session, project, name="Idle")
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, busy, date(2026, 9, 4), 4)

    body = (await client.post(URL, json=_body(project, busy, idle))).json()

    assert [item["name"] for item in body["lines"]] == ["Busy"]
    assert [item["name"] for item in body["omitted"]] == ["Idle"]


async def test_a_deactivated_consultants_hours_still_count(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 7), 8)
    consultant.is_active = False
    await db_session.commit()

    body = (await client.post(URL, json=_body(project, line))).json()

    assert Decimal(body["lines"][0]["quantity"]) == 8


async def test_unlocked_days_are_warned_about(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)
    consultant = await make_consultant(db_session)
    other = await make_consultant(db_session, "d@example.com")
    for day in (8, 9, 10):
        await log_hours(db_session, consultant, line, date(2026, 9, day), 8)
    # Same day as another unlocked entry: still one day.
    await log_hours(db_session, other, line, date(2026, 9, 10), 4)
    await log_hours(db_session, consultant, line, date(2026, 9, 11), 8, locked=True)

    body = (await client.post(URL, json=_body(project, line))).json()

    unlocked = [w for w in body["warnings"] if w["code"] == "unlocked_hours"]
    assert unlocked[0]["service_lines"][0]["days"] == 3


async def test_generation_never_changes_lock_states(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 1), 8, locked=True)
    await log_hours(db_session, consultant, line, date(2026, 9, 2), 8)

    await client.post(URL, json=_body(project, line))

    db_session.expire_all()
    locks = (
        await db_session.execute(
            select(TimeEntry.date, TimeEntry.is_locked).order_by(TimeEntry.date)
        )
    ).all()
    assert [locked for _, locked in locks] == [True, False]


async def test_an_inactive_or_foreign_service_line_is_422(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    other = await make_project(db_session, name="Other")
    inactive = await add_service_line(db_session, project, is_active=False)
    foreign = await add_service_line(db_session, other)

    assert (await client.post(URL, json=_body(project, inactive))).status_code == 422
    assert (await client.post(URL, json=_body(project, foreign))).status_code == 422


async def test_an_invalid_period_is_422(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)

    too_long = _body(project, line, period_start="2025-01-01", period_end="2026-01-02")
    backwards = _body(project, line, period_start="2026-09-30", period_end="2026-09-01")
    assert (await client.post(URL, json=too_long)).status_code == 422
    assert (await client.post(URL, json=backwards)).status_code == 422


async def test_generation_requires_billing(client, db_session) -> None:
    await login(client, db_session, "manager")
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)

    assert (await client.post(URL, json=_body(project, line))).status_code == 403
