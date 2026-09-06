from datetime import UTC, date, datetime, timedelta

from app.models.project import Project
from app.models.time_entry import TimeEntry
from tests.factories import create_company, create_currency, create_user


async def _login_manager(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="project_admin@example.com",
        password="project_admin-pass",
        role_name="project_admin",
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": "project_admin@example.com", "password": "project_admin-pass"},
    )
    assert response.status_code == 200


async def _setup_refs(db_session):
    vendor = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    client_company = await create_company(
        db_session, legal_name="Beta Client", is_vendor=False
    )
    currency = await create_currency(db_session, alpha_code="USD", numeric_code="840")
    return vendor, client_company, currency


def _project_payload(vendor, client_company, currency, **overrides):
    payload = {
        "name": "Acme ERP Rollout",
        "vendor_company_id": str(vendor.id),
        "client_company_id": str(client_company.id),
        "invoicing_currency": currency.alpha_code,
        "project_type": "time_and_material",
    }
    payload.update(overrides)
    return payload


async def test_list_projects_requires_auth(client, db_session) -> None:
    response = await client.get("/api/projects")
    assert response.status_code == 401


async def test_list_projects_rejects_consultant(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="consultant@example.com",
        password="pw",
        role_name="consultant",
    )
    await client.post(
        "/api/auth/login", json={"email": "consultant@example.com", "password": "pw"}
    )
    response = await client.get("/api/projects")
    assert response.status_code == 403


async def test_list_projects_rejects_administrator_without_manager_role(
    client, db_session
) -> None:
    # `projects` is granted by the literal `project_admin` role only — not inferred from
    # `administrator` (see docs/requirements/user.md#role--screen-access).
    await create_user(
        db_session,
        name_id="admin-only@example.com",
        password="pw",
        role_name="administrator",
    )
    await client.post(
        "/api/auth/login", json={"email": "admin-only@example.com", "password": "pw"}
    )
    response = await client.get("/api/projects")
    assert response.status_code == 403


async def test_create_and_list_project(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Acme ERP Rollout"
    assert body["status"] == "draft"
    assert body["is_active"] is True
    assert body["total_value"] == "0.0000"
    assert body["service_lines"] == []

    listing = await client.get("/api/projects")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Acme ERP Rollout"
    assert payload["items"][0]["vendor_company_name"] == "Acme Vendor"
    assert payload["items"][0]["client_company_name"] == "Beta Client"


async def test_list_projects_sort_composes_with_pagination(client, db_session) -> None:
    # Sorting must happen server-side, before pagination splits rows into pages —
    # a client-side-only sort only reorders whatever page is already in memory,
    # which silently breaks once there's more than one page, since the default
    # order (created_at desc) has no relation to name order. See
    # docs/requirements/project.md#projects-list-screen.
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    for i in range(55):
        db_session.add(
            Project(
                name=f"Project {i:03d}",
                vendor_company_id=vendor.id,
                client_company_id=client_company.id,
                invoicing_currency=currency.alpha_code,
                project_type="time_and_material",
                # Deliberately the reverse of name order, so a passing test proves
                # sorting is real (not just coincidentally matching created_at).
                created_at=datetime.now(UTC) - timedelta(seconds=i),
            )
        )
    await db_session.commit()

    page1 = await client.get(
        "/api/projects", params={"page": 1, "sort_by": "name", "sort_dir": "asc"}
    )
    page2 = await client.get(
        "/api/projects", params={"page": 2, "sort_by": "name", "sort_dir": "asc"}
    )
    assert page1.status_code == 200
    page1_names = [item["name"] for item in page1.json()["items"]]
    page2_names = [item["name"] for item in page2.json()["items"]]

    assert page1_names[0] == "Project 000"
    assert page1_names == sorted(page1_names)
    assert page2_names == sorted(page2_names)
    # Contiguous under the requested sort: page 2 must pick up exactly where
    # page 1 left off, not restart or skip.
    assert page2_names[0] > page1_names[-1]


async def test_list_projects_unknown_sort_by_falls_back_to_default(
    client, db_session
) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    older = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency, name="Older")
    )
    assert older.status_code == 201
    newer = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency, name="Newer")
    )
    assert newer.status_code == 201

    response = await client.get("/api/projects", params={"sort_by": "not_a_real_column"})
    assert response.status_code == 200
    # Falls back to the existing default (created_at desc) — the more recently
    # created project comes first.
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["Newer", "Older"]


async def test_create_project_rejects_non_vendor_company(client, db_session) -> None:
    await _login_manager(client, db_session)
    _vendor, client_company, currency = await _setup_refs(db_session)

    response = await client.post(
        "/api/projects",
        json=_project_payload(client_company, client_company, currency),
    )
    assert response.status_code == 422


async def test_create_project_rejects_disabled_currency(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, _currency = await _setup_refs(db_session)
    disabled = await create_currency(
        db_session, alpha_code="XYZ", numeric_code="999", is_enabled=False
    )

    response = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, disabled)
    )
    assert response.status_code == 422


async def test_create_project_rejects_empty_name(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)

    response = await client.post(
        "/api/projects",
        json=_project_payload(vendor, client_company, currency, name="   "),
    )
    assert response.status_code == 422


async def test_deactivate_project_removes_it_from_list(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]

    deactivate = await client.post(f"/api/projects/{project_id}/deactivate")
    assert deactivate.status_code == 204

    listing = await client.get("/api/projects")
    assert listing.json()["total"] == 0

    get_response = await client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 404


async def test_service_line_crud_and_value_calculation(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    await create_user(
        db_session,
        name_id="consultant@example.com",
        password="pw",
        role_name="consultant",
    )
    consultants = await client.get("/api/users", params={"role": "consultant"})
    consultant_id = consultants.json()["items"][0]["id"]

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]

    add_line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "name": "Discovery phase",
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [consultant_id],
        },
    )
    assert add_line.status_code == 201
    line = add_line.json()
    assert line["name"] == "Discovery phase"
    assert line["value"] == "1000.0000"
    assert line["users"][0]["id"] == consultant_id

    detail = await client.get(f"/api/projects/{project_id}")
    assert detail.json()["total_value"] == "1000.0000"

    line_id = line["id"]
    update_line = await client.patch(
        f"/api/projects/{project_id}/service-lines/{line_id}",
        json={
            "name": "Build phase",
            "quantity": "5",
            "uom": "days",
            "unit_price": "50.00",
            "user_ids": [],
        },
    )
    assert update_line.status_code == 200
    assert update_line.json()["name"] == "Build phase"
    assert update_line.json()["value"] == "250.0000"

    delete_line = await client.delete(
        f"/api/projects/{project_id}/service-lines/{line_id}"
    )
    assert delete_line.status_code == 204

    detail_after = await client.get(f"/api/projects/{project_id}")
    assert detail_after.json()["service_lines"] == []
    assert detail_after.json()["total_value"] == "0.0000"


async def test_service_line_name_is_optional(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]

    add_line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={"quantity": "1", "uom": "hours", "unit_price": "1.00", "user_ids": []},
    )
    assert add_line.status_code == 201
    assert add_line.json()["name"] is None


async def test_service_line_rejects_non_consultant_user(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    non_consultant = await create_user(
        db_session,
        name_id="other-admin@example.com",
        password="pw",
        role_name="administrator",
    )

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]

    response = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [str(non_consultant.id)],
        },
    )
    assert response.status_code == 422


async def test_duplicate_project_copies_service_lines_and_resets_to_draft(
    client, db_session
) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]
    await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "name": "Discovery phase",
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [],
        },
    )
    await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, status="active"),
    )

    duplicate = await client.post(f"/api/projects/{project_id}/duplicate")
    assert duplicate.status_code == 200
    body = duplicate.json()
    assert body["status"] == "draft"
    assert len(body["service_lines"]) == 1
    assert body["service_lines"][0]["name"] == "Discovery phase"
    assert body["service_lines"][0]["value"] == "1000.0000"


async def test_create_and_update_project_managers(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    pm1 = await create_user(
        db_session, name_id="pm1@example.com", password="pw", role_name="project_manager"
    )
    pm2 = await create_user(
        db_session, name_id="pm2@example.com", password="pw", role_name="project_manager"
    )

    create = await client.post(
        "/api/projects",
        json=_project_payload(
            vendor, client_company, currency, project_manager_ids=[str(pm1.id)]
        ),
    )
    assert create.status_code == 201
    body = create.json()
    assert [pm["id"] for pm in body["project_managers"]] == [str(pm1.id)]
    assert body["project_managers"][0]["full_name"] == pm1.full_name

    project_id = body["id"]
    update = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(
            vendor,
            client_company,
            currency,
            project_manager_ids=[str(pm1.id), str(pm2.id)],
        ),
    )
    assert update.status_code == 200
    assert {pm["id"] for pm in update.json()["project_managers"]} == {
        str(pm1.id),
        str(pm2.id),
    }

    cleared = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, project_manager_ids=[]),
    )
    assert cleared.status_code == 200
    assert cleared.json()["project_managers"] == []


async def test_project_rejects_non_project_manager_user(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    consultant = await create_user(
        db_session, name_id="not-a-pm@example.com", password="pw", role_name="consultant"
    )

    response = await client.post(
        "/api/projects",
        json=_project_payload(
            vendor, client_company, currency, project_manager_ids=[str(consultant.id)]
        ),
    )
    assert response.status_code == 422


async def test_duplicate_project_copies_project_managers(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    pm = await create_user(
        db_session, name_id="pm@example.com", password="pw", role_name="project_manager"
    )

    create = await client.post(
        "/api/projects",
        json=_project_payload(
            vendor, client_company, currency, project_manager_ids=[str(pm.id)]
        ),
    )
    project_id = create.json()["id"]

    duplicate = await client.post(f"/api/projects/{project_id}/duplicate")
    assert duplicate.status_code == 200
    assert [p["id"] for p in duplicate.json()["project_managers"]] == [str(pm.id)]


async def test_closed_project_blocks_project_manager_reassignment(
    client, db_session
) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    pm = await create_user(
        db_session, name_id="pm-closed@example.com", password="pw", role_name="project_manager"
    )

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]
    close = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, status="closed"),
    )
    assert close.status_code == 200

    blocked = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(
            vendor,
            client_company,
            currency,
            status="closed",
            project_manager_ids=[str(pm.id)],
        ),
    )
    assert blocked.status_code == 409


async def test_closed_project_blocks_edits_except_status(client, db_session) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]
    close = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, status="closed"),
    )
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    blocked_edit = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(
            vendor, client_company, currency, status="closed", name="Renamed"
        ),
    )
    assert blocked_edit.status_code == 409

    blocked_add_line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={"quantity": "1", "uom": "hours", "unit_price": "1.00", "user_ids": []},
    )
    assert blocked_add_line.status_code == 409

    reopen = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, status="active"),
    )
    assert reopen.status_code == 200
    assert reopen.json()["status"] == "active"


async def test_active_project_blocks_service_line_delete_with_logged_time(
    client, db_session
) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)
    consultant = await create_user(
        db_session,
        name_id="consultant-logged@example.com",
        password="pw",
        role_name="consultant",
    )

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]
    add_line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [str(consultant.id)],
        },
    )
    line_id = add_line.json()["id"]

    activate = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, status="active"),
    )
    assert activate.status_code == 200

    db_session.add(
        TimeEntry(
            user_id=consultant.id,
            service_line_id=line_id,
            date=date(2026, 1, 5),
            time_entry=timedelta(hours=8),
        )
    )
    await db_session.commit()

    delete_line = await client.delete(
        f"/api/projects/{project_id}/service-lines/{line_id}"
    )
    assert delete_line.status_code == 409

    # Editing remains allowed — only deletion is blocked (see
    # docs/requirements/project.md#validation-rules-1).
    update_line = await client.patch(
        f"/api/projects/{project_id}/service-lines/{line_id}",
        json={
            "quantity": "5",
            "uom": "hours",
            "unit_price": "100.00",
            "user_ids": [str(consultant.id)],
        },
    )
    assert update_line.status_code == 200

    detail = await client.get(f"/api/projects/{project_id}")
    assert len(detail.json()["service_lines"]) == 1


async def test_active_project_allows_service_line_delete_without_logged_time(
    client, db_session
) -> None:
    await _login_manager(client, db_session)
    vendor, client_company, currency = await _setup_refs(db_session)

    create = await client.post(
        "/api/projects", json=_project_payload(vendor, client_company, currency)
    )
    project_id = create.json()["id"]
    add_line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={"quantity": "10", "uom": "hours", "unit_price": "100.00", "user_ids": []},
    )
    line_id = add_line.json()["id"]

    activate = await client.patch(
        f"/api/projects/{project_id}",
        json=_project_payload(vendor, client_company, currency, status="active"),
    )
    assert activate.status_code == 200

    delete_line = await client.delete(
        f"/api/projects/{project_id}/service-lines/{line_id}"
    )
    assert delete_line.status_code == 204

    detail = await client.get(f"/api/projects/{project_id}")
    assert detail.json()["service_lines"] == []
