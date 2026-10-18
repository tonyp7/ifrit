from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from tests.invoice_helpers import (
    add_milestone,
    add_service_line,
    log_hours,
    login,
    make_consultant,
    make_project,
)

URL = "/api/invoices/generate"
SEPTEMBER = {"period_start": "2026-09-01", "period_end": "2026-09-30"}


def _body(project, *lines, **overrides) -> dict[str, object]:
    return {
        "kind": "time",
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


# --- Fixed Price -----------------------------------------------------------------


def _milestone_body(project, *milestones) -> dict[str, object]:
    return {
        "kind": "milestone",
        "project_id": str(project.id),
        "milestone_ids": [str(milestone.id) for milestone in milestones],
    }


async def _invoice_count(db_session) -> int:
    return (await db_session.execute(select(func.count(Invoice.id)))).scalar_one()


async def test_milestone_line(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session, project_type="fixed_price")
    milestone = await add_milestone(
        db_session, project, "Phase 2 – Delivery of beta", "12000"
    )

    response = await client.post(URL, json=_milestone_body(project, milestone))

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["name"] == "Phase 2 – Delivery of beta"
    assert (Decimal(line["quantity"]), line["uom"]) == (1, "ea")
    assert Decimal(line["unit_price"]) == Decimal(12000)
    assert body["omitted"] == [] and body["warnings"] == []
    assert await _invoice_count(db_session) == 0


async def test_several_milestones_come_out_in_milestone_order(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session, project_type="fixed_price")
    down = await add_milestone(db_session, project, "Downpayment", "57600", position=0)
    await add_milestone(db_session, project, "End of SIT", "38400", position=1)
    end = await add_milestone(db_session, project, "Project end", "57600", position=2)

    # Ticked last first, and the first one twice.
    response = await client.post(URL, json=_milestone_body(project, end, down, down))

    assert response.status_code == 200, response.text
    lines = response.json()["lines"]
    assert [(line["name"], Decimal(line["unit_price"])) for line in lines] == [
        ("Downpayment", 57600),
        ("Project end", 57600),
    ]
    assert all((Decimal(line["quantity"]), line["uom"]) == (1, "ea") for line in lines)
    assert await _invoice_count(db_session) == 0


async def test_milestone_and_project_type_must_match(client, db_session) -> None:
    await login(client, db_session)
    fixed = await make_project(db_session, project_type="fixed_price")
    other = await make_project(db_session, name="Other", project_type="fixed_price")
    tm = await make_project(db_session, name="T&M")
    mine = await add_milestone(db_session, fixed, "Phase 1", "100")
    foreign = await add_milestone(db_session, other, "Elsewhere", "100")
    tm_line = await add_service_line(db_session, tm)
    fixed_line = await add_service_line(db_session, fixed)

    foreign_among_mine = _milestone_body(fixed, mine, foreign)
    no_milestone = _milestone_body(fixed)
    milestone_on_tm = {**_milestone_body(fixed, mine), "project_id": str(tm.id)}
    time_on_fixed = _body(fixed, fixed_line)
    for body in (foreign_among_mine, no_milestone, milestone_on_tm, time_on_fixed):
        assert (await client.post(URL, json=body)).status_code == 422
    # The time kind still works on a T&M project.
    assert (await client.post(URL, json=_body(tm, tm_line))).status_code == 200
    assert await _invoice_count(db_session) == 0


async def test_a_milestone_line_outlives_its_milestone(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session, project_type="fixed_price")
    milestone = await add_milestone(db_session, project, "Phase 2", "12000")
    generated = (
        await client.post(URL, json=_milestone_body(project, milestone))
    ).json()["lines"][0]
    line = {
        "description": generated["name"],
        "quantity": generated["quantity"],
        "uom": generated["uom"],
        "unit_price": generated["unit_price"],
    }
    draft_body = {
        "project_id": str(project.id),
        "bill_from": {"name": "Ifrit"},
        "bill_to": {"name": "ACME"},
        "lines": [line],
    }
    draft = (await client.post("/api/invoices", json=draft_body)).json()
    issued = (await client.post("/api/invoices", json=draft_body)).json()
    assert (await client.post(f"/api/invoices/{issued['id']}/issue")).status_code == 200

    milestone.value = Decimal(13000)
    await db_session.commit()
    after_edit = (await client.get(f"/api/invoices/{draft['id']}")).json()
    await db_session.delete(milestone)
    await db_session.commit()
    after_delete = (await client.get(f"/api/invoices/{issued['id']}")).json()

    assert Decimal(after_edit["lines"][0]["unit_price"]) == Decimal(12000)
    assert Decimal(after_edit["total"]) == Decimal(12000)
    assert after_delete["lines"][0]["description"] == "Phase 2"
    assert Decimal(after_delete["total"]) == Decimal(12000)
