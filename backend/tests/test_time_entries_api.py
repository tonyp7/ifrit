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


async def _setup_project_with_consultant_and_pm(
    client, db_session, *, consultant_name_id: str, pm_name_id: str, project_name: str = "Acme Rollout"
):
    """Same as _setup_project_with_consultant, plus a project_manager assigned to
    the project — needed for the Validation-screen endpoints (GET
    /time-entries/managed, PUT /time-entries/lock, and PUT /time-entries'
    override path)."""
    await create_user(
        db_session, name_id=consultant_name_id, password="pw", role_name="consultant"
    )
    await create_user(
        db_session, name_id=pm_name_id, password="pw", role_name="project_manager"
    )
    await client.post(
        "/api/auth/login",
        json={"email": "project_admin@example.com", "password": "project_admin-pw"},
    )
    vendor = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    client_company = await create_company(db_session, legal_name="Beta Client")
    currency = await create_currency(db_session, alpha_code="USD", numeric_code="840")

    users = (await client.get("/api/users", params={"page": 1})).json()["items"]
    consultant_id = next(u["id"] for u in users if u["name_id"] == consultant_name_id)
    pm_id = next(u["id"] for u in users if u["name_id"] == pm_name_id)

    project = await client.post(
        "/api/projects",
        json={
            "name": project_name,
            "vendor_company_id": str(vendor.id),
            "client_company_id": str(client_company.id),
            "invoicing_currency": currency.alpha_code,
            "project_type": "time_and_material",
            "status": "active",
            "project_manager_ids": [pm_id],
        },
    )
    project_id = project.json()["id"]

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
    return project_id, service_line_id, consultant_id, pm_id


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

    # No Validation/lock endpoint exists yet (see specs/requirements/timesheet.md's
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
    # specs/requirements/timesheet.md's "API contract").
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


# --- Validation screen: GET /time-entries/managed ---------------------------------


async def test_managed_requires_project_manager_role(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, _service_line_id, _consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    # project_admin alone (not project_manager) must be rejected.
    await _login_as(client, "project_admin@example.com", "project_admin-pw")
    response = await client.get(
        "/api/time-entries/managed",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert response.status_code == 403


async def test_managed_lists_consultants_including_zero_data(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    # A second consultant assigned to the line but with zero logged time.
    await create_user(db_session, name_id="c2@example.com", password="pw", role_name="consultant")
    await _login_as(client, "project_admin@example.com", "project_admin-pw")
    c2 = next(
        u["id"]
        for u in (await client.get("/api/users", params={"page": 1})).json()["items"]
        if u["name_id"] == "c2@example.com"
    )
    await client.patch(
        f"/api/projects/{project_id}/service-lines/{service_line_id}",
        json={
            "name": "Discovery",
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [consultant_id, c2],
        },
    )

    await _login_as(client, "c@example.com")
    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    await _login_as(client, "pm@example.com")
    response = await client.get(
        "/api/time-entries/managed",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert response.status_code == 200
    consultants = {c["user_id"]: c for c in response.json()["consultants"]}
    assert consultant_id in consultants
    assert c2 in consultants
    assert len(consultants[consultant_id]["entries"]) == 1
    assert consultants[consultant_id]["entries"][0]["hours"] == "3.00"
    # Zero-data consultant still gets a slot, with an empty entries list and the
    # eligible service line ready to add — see
    # specs/requirements/timesheet.md's Validation § Scope.
    assert consultants[c2]["entries"] == []
    assert [l["service_line_id"] for l in consultants[c2]["eligible_service_lines"]] == [
        service_line_id
    ]


async def test_managed_excludes_projects_outside_scope(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    await _setup_project_with_consultant_and_pm(
        client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
    )
    # A second project the pm is NOT assigned to, with its own consultant.
    await create_user(
        db_session, name_id="outside@example.com", password="pw", role_name="consultant"
    )
    await _login_as(client, "project_admin@example.com", "project_admin-pw")
    vendor = await create_company(db_session, legal_name="Other Vendor", is_vendor=True)
    client_company = await create_company(db_session, legal_name="Other Client")
    currency = (
        await client.get("/api/currencies")
    ).json()
    outside_id = next(
        u["id"]
        for u in (await client.get("/api/users", params={"page": 1})).json()["items"]
        if u["name_id"] == "outside@example.com"
    )
    other_project = await client.post(
        "/api/projects",
        json={
            "name": "Other Project",
            "vendor_company_id": str(vendor.id),
            "client_company_id": str(client_company.id),
            "invoicing_currency": currency[0]["alpha_code"],
            "project_type": "time_and_material",
            "status": "active",
        },
    )
    await client.post(
        f"/api/projects/{other_project.json()['id']}/service-lines",
        json={
            "name": "Other Line",
            "quantity": "5",
            "uom": "hours",
            "unit_price": "50.00",
            "user_ids": [outside_id],
        },
    )

    await _login_as(client, "pm@example.com")
    response = await client.get(
        "/api/time-entries/managed",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert outside_id not in {c["user_id"] for c in response.json()["consultants"]}


async def test_managed_includes_historical_consultant_after_unassignment(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await _login_as(client, "c@example.com")
    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    # project_admin unassigns the consultant from the service line entirely.
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

    await _login_as(client, "pm@example.com")
    response = await client.get(
        "/api/time-entries/managed",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    consultants = {c["user_id"]: c for c in response.json()["consultants"]}
    assert consultant_id in consultants
    assert len(consultants[consultant_id]["entries"]) == 1
    # No longer eligible to be added to — see specs/requirements/timesheet.md's
    # "Unassigned" cell state, derived client-side from this exact field.
    assert consultants[consultant_id]["eligible_service_lines"] == []


# --- Validation screen: PUT /time-entries/lock -------------------------------------


async def test_lock_materializes_gaps_and_preserves_existing_value(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await _login_as(client, "c@example.com")
    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    await _login_as(client, "pm@example.com")
    lock = await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": consultant_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-04",
            "end_date": "2026-08-06",
            "locked": True,
        },
    )
    assert lock.status_code == 200
    by_date = {e["date"]: e for e in lock.json()}
    assert len(by_date) == 3
    assert by_date["2026-08-05"]["hours"] == "3.00"
    assert by_date["2026-08-05"]["is_locked"] is True
    assert by_date["2026-08-04"]["hours"] == "0.00"
    assert by_date["2026-08-04"]["is_locked"] is True
    assert by_date["2026-08-06"]["hours"] == "0.00"
    assert by_date["2026-08-06"]["is_locked"] is True

    # The consultant's own write path rejects all three now, regardless of which
    # ones were pre-existing vs. gap-filled.
    await _login_as(client, "c@example.com")
    blocked = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-04", "hours": "1"}],
    )
    assert blocked.status_code == 207
    assert blocked.json()[0]["error"] == "locked"


async def test_unlock_deletes_gap_rows_and_unlocks_real_ones(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await _login_as(client, "c@example.com")
    await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"}],
    )

    await _login_as(client, "pm@example.com")
    await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": consultant_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-04",
            "end_date": "2026-08-06",
            "locked": True,
        },
    )
    unlock = await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": consultant_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-04",
            "end_date": "2026-08-06",
            "locked": False,
        },
    )
    assert unlock.status_code == 200
    by_date = {e["date"]: e for e in unlock.json()}
    # The two gap-fill rows are gone entirely, not left as unlocked zeros.
    assert set(by_date.keys()) == {"2026-08-05"}
    assert by_date["2026-08-05"]["hours"] == "3.00"
    assert by_date["2026-08-05"]["is_locked"] is False

    # The consultant can edit it again now.
    await _login_as(client, "c@example.com")
    edit = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": service_line_id, "date": "2026-08-05", "hours": "5"}],
    )
    assert edit.status_code == 200
    assert edit.json()[0]["ok"] is True


async def test_lock_rejects_non_project_manager(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await _login_as(client, "project_admin@example.com", "project_admin-pw")
    response = await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": consultant_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "locked": True,
        },
    )
    assert response.status_code == 403


async def test_lock_rejects_project_manager_without_project_assignment(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await create_user(
        db_session, name_id="other-pm@example.com", password="pw", role_name="project_manager"
    )
    await _login_as(client, "other-pm@example.com")
    response = await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": consultant_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "locked": True,
        },
    )
    assert response.status_code == 403


async def test_lock_rejects_unassigned_consultant(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, _consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await create_user(
        db_session, name_id="not-assigned@example.com", password="pw", role_name="consultant"
    )
    await _login_as(client, "project_admin@example.com", "project_admin-pw")
    not_assigned_id = next(
        u["id"]
        for u in (await client.get("/api/users", params={"page": 1})).json()["items"]
        if u["name_id"] == "not-assigned@example.com"
    )

    await _login_as(client, "pm@example.com")
    response = await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": not_assigned_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "locked": True,
        },
    )
    assert response.status_code == 403


# --- project_manager override via PUT /time-entries --------------------------------


async def test_override_allows_project_manager_to_edit_consultant_entry(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await _login_as(client, "pm@example.com")
    response = await client.put(
        "/api/time-entries",
        json=[
            {
                "service_line_id": service_line_id,
                "date": "2026-08-05",
                "hours": "4",
                "user_id": consultant_id,
            }
        ],
    )
    assert response.status_code == 200
    assert response.json()[0]["ok"] is True
    assert response.json()[0]["entry"]["hours"] == "4.00"

    await _login_as(client, "c@example.com")
    listing = await client.get(
        "/api/time-entries",
        params={"start_date": "2026-08-01", "end_date": "2026-08-31"},
    )
    assert listing.json()["items"][0]["hours"] == "4.00"


async def test_override_rejects_non_project_manager(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await create_user(
        db_session, name_id="other-consultant@example.com", password="pw", role_name="consultant"
    )
    await _login_as(client, "other-consultant@example.com")
    response = await client.put(
        "/api/time-entries",
        json=[
            {
                "service_line_id": service_line_id,
                "date": "2026-08-05",
                "hours": "4",
                "user_id": consultant_id,
            }
        ],
    )
    assert response.status_code == 207
    assert response.json()[0]["ok"] is False
    assert response.json()[0]["error"] == "not_authorized"


async def test_override_rejects_project_manager_without_project_assignment(
    client, db_session
) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await create_user(
        db_session, name_id="other-pm2@example.com", password="pw", role_name="project_manager"
    )
    await _login_as(client, "other-pm2@example.com")
    response = await client.put(
        "/api/time-entries",
        json=[
            {
                "service_line_id": service_line_id,
                "date": "2026-08-05",
                "hours": "4",
                "user_id": consultant_id,
            }
        ],
    )
    assert response.status_code == 207
    assert response.json()[0]["ok"] is False
    assert response.json()[0]["error"] == "not_authorized"


async def test_override_respects_lock(client, db_session) -> None:
    await _login_manager_first(client, db_session)
    _project_id, service_line_id, consultant_id, _pm_id = (
        await _setup_project_with_consultant_and_pm(
            client, db_session, consultant_name_id="c@example.com", pm_name_id="pm@example.com"
        )
    )
    await _login_as(client, "pm@example.com")
    await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": consultant_id,
            "service_line_id": service_line_id,
            "start_date": "2026-08-05",
            "end_date": "2026-08-05",
            "locked": True,
        },
    )
    response = await client.put(
        "/api/time-entries",
        json=[
            {
                "service_line_id": service_line_id,
                "date": "2026-08-05",
                "hours": "4",
                "user_id": consultant_id,
            }
        ],
    )
    assert response.status_code == 207
    assert response.json()[0]["error"] == "locked"
