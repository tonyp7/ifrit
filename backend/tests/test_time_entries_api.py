from tests.factories import create_company, create_currency, create_user


async def _login(client, db_session, *, name_id: str, role_name: str) -> None:
    await create_user(db_session, name_id=name_id, password="pw", role_name=role_name)
    response = await client.post(
        "/api/auth/login", json={"email": name_id, "password": "pw"}
    )
    assert response.status_code == 200


async def _setup_project_with_consultant(
    client, db_session, *, consultant_name_id: str
):
    await create_user(
        db_session, name_id=consultant_name_id, password="pw", role_name="consultant"
    )
    await client.post(
        "/api/auth/login",
        json={"email": "project_admin@example.com", "password": "project_admin-pw"},
    )
    vendor = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    client_company = await create_company(db_session, legal_name="Beta Client")
    currency = await create_currency(db_session, alpha_code="USD", numeric_code="840")

    project = await client.post(
        "/api/projects",
        json={
            "name": "Acme Rollout",
            "vendor_company_id": str(vendor.id),
            "client_company_id": str(client_company.id),
            "invoicing_currency": currency.alpha_code,
            "project_type": "time_and_material",
            "status": "active",
        },
    )
    project_id = project.json()["id"]

    consultants = await client.get("/api/users", params={"role": "consultant"})
    consultant_id = next(
        u["id"]
        for u in consultants.json()["items"]
        if u["name_id"] == consultant_name_id
    )

    line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "name": "Discovery",
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [consultant_id],
        },
    )
    service_line_id = line.json()["id"]
    return project_id, service_line_id


async def _login_manager_first(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="project_admin@example.com",
        password="project_admin-pw",
        role_name="project_admin",
    )


async def _login_as(client, name_id: str, password: str = "pw") -> None:
    response = await client.post(
        "/api/auth/login", json={"email": name_id, "password": password}
    )
    assert response.status_code == 200


async def test_time_entries_require_auth(client, db_session) -> None:
    response = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert response.status_code == 401


async def test_upsert_and_list_time_entry(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")

    upsert = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "1.5"}],
    )
    assert upsert.status_code == 200
    results = upsert.json()
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["service_line_id"] == service_line_id
    assert results[0]["date"] == "2026-08-05"
    entry = results[0]["entry"]
    assert entry["hours"] == "1.50"
    assert entry["is_locked"] is False
    assert entry["service_line_name"] == "Discovery"
    assert entry["project_name"] == "Acme Rollout"

    listing = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["date"] == "2026-08-05"
    assert items[0]["hours"] == "1.50"


async def test_upsert_zero_deletes_existing_entry(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")

    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "2"}],
    )
    zero = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "0"}],
    )
    assert zero.status_code == 200
    results = zero.json()
    assert results == [
        {
            "service_line_id": service_line_id,
            "date": "2026-08-05",
            "ok": True,
            "entry": None,
            "error": None,
        }
    ]

    listing = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert listing.json()["items"] == []


async def test_upsert_rejects_invalid_hours(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")

    # Malformed hours (out of range / not a half-step) fail Pydantic validation on the
    # request item itself — a 422 for the whole request, distinct from a per-item
    # {ok: false} outcome (which is for otherwise-valid items rejected by business
    # rules — locked, not eligible).
    too_high = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "25"}],
    )
    assert too_high.status_code == 422

    not_half_step = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "1.3"}],
    )
    assert not_half_step.status_code == 422


async def test_upsert_rejects_unassigned_service_line(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="assigned@example.com"
    )
    await create_user(
        db_session,
        name_id="outsider@example.com",
        password="pw",
        role_name="consultant",
    )
    await _login_as(client, "outsider@example.com")

    response = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "1"}],
    )
    assert response.status_code == 207
    results = response.json()
    assert results == [
        {
            "service_line_id": service_line_id,
            "date": "2026-08-05",
            "ok": False,
            "entry": None,
            "error": "not_eligible",
        }
    ]


async def test_upsert_rejects_locked_entry_regardless_of_direction(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")

    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    # No Validation/lock endpoint exists yet (see docs/requirements/timesheet.md's
    # Validation placeholder) — lock the row directly for this test.
    from sqlalchemy import update

    from app.models.time_entry import TimeEntry

    await db_session.execute(
        update(TimeEntry)
        .where(TimeEntry.service_line_id == service_line_id)
        .values(is_locked=True)
    )
    await db_session.commit()

    # Attempting to overwrite a locked entry is rejected...
    overwrite = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "5"}],
    )
    assert overwrite.status_code == 207
    assert overwrite.json() == [
        {
            "service_line_id": service_line_id,
            "date": "2026-08-05",
            "ok": False,
            "entry": None,
            "error": "locked",
        }
    ]

    # ...and so is attempting to delete (zero out) one — regardless of direction, a
    # locked row is immutable through this endpoint (see
    # docs/requirements/timesheet.md's "API contract").
    delete_attempt = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "0"}],
    )
    assert delete_attempt.status_code == 207
    assert delete_attempt.json()[0]["ok"] is False
    assert delete_attempt.json()[0]["error"] == "locked"

    # The entry is untouched by either attempt.
    listing = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["hours"] == "3.00"
    assert items[0]["is_locked"] is True


async def test_bulk_upsert_processes_items_independently(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")

    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    from sqlalchemy import update

    from app.models.time_entry import TimeEntry

    await db_session.execute(
        update(TimeEntry)
        .where(TimeEntry.service_line_id == service_line_id)
        .values(is_locked=True)
    )
    await db_session.commit()

    # A single bulk request: one item clears a locked day (must fail), one clears an
    # untouched day (must succeed) — this is exactly the shape the clear-on-remove
    # flow sends. Neither item's outcome should affect the other.
    response = await client.put(
        "/api/time-entries",
        json=[
            {"service_line_id": service_line_id, "date": "2026-08-05", "hours": "0"},
            {"service_line_id": service_line_id, "date": "2026-08-06", "hours": "4"},
        ],
    )
    assert response.status_code == 207
    results = {r["date"]: r for r in response.json()}
    assert results["2026-08-05"]["ok"] is False
    assert results["2026-08-05"]["error"] == "locked"
    assert results["2026-08-06"]["ok"] is True
    assert results["2026-08-06"]["entry"]["hours"] == "4.00"

    listing = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    items = {i["date"]: i for i in listing.json()["items"]}
    assert items["2026-08-05"]["is_locked"] is True
    assert items["2026-08-06"]["hours"] == "4.00"


async def test_eligible_service_lines_lists_only_assigned_active_lines(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")

    eligible = await client.get("/api/time-entries/eligible-service-lines")
    assert eligible.status_code == 200
    items = eligible.json()["items"]
    assert len(items) == 1
    assert items[0]["service_line_id"] == service_line_id
    assert items[0]["project_name"] == "Acme Rollout"


async def test_entries_remain_visible_after_unassignment(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    project_id, service_line_id = await _setup_project_with_consultant(
        client, db_session, consultant_name_id="consultant@example.com"
    )
    await _login_as(client, "consultant@example.com")
    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    # Manager unassigns the consultant from the service line entirely.
    await _login_as(client, "project_admin@example.com", "project_admin-pw")
    await client.patch(
        f"/api/projects/{project_id}/service-lines/{service_line_id}",
        json={
            "name": "Discovery",
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [],
        },
    )

    await _login_as(client, "consultant@example.com")
    listing = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert len(listing.json()["items"]) == 1

    eligible = await client.get("/api/time-entries/eligible-service-lines")
    assert eligible.json()["items"] == []

    blocked = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-06", "hours": "1"}],
    )
    assert blocked.status_code == 207
    assert blocked.json()[0]["ok"] is False
    assert blocked.json()[0]["error"] == "not_eligible"
