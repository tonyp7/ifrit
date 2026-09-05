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
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "1.5"},
    )
    assert upsert.status_code == 200
    body = upsert.json()
    assert body["hours"] == "1.50"
    assert body["is_locked"] is False
    assert body["service_line_name"] == "Discovery"
    assert body["project_name"] == "Acme Rollout"

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
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "2"},
    )
    zero = await client.put(
        "/api/time-entries",
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "0"},
    )
    assert zero.status_code == 200
    assert zero.json() is None

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

    too_high = await client.put(
        "/api/time-entries",
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "25"},
    )
    assert too_high.status_code == 422

    not_half_step = await client.put(
        "/api/time-entries",
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "1.3"},
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
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "1"},
    )
    assert response.status_code == 422


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
        json={"service_line_id": service_line_id, "date": "2026-08-05", "hours": "3"},
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
        json={"service_line_id": service_line_id, "date": "2026-08-06", "hours": "1"},
    )
    assert blocked.status_code == 422
