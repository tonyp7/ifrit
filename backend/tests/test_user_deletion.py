"""Deleting (deactivating) a user: project-manager cleanup, its DB-trigger backstop,
and how a deleted consultant behaves on service lines and timesheets."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models.project import project_manager_assignments
from app.schemas.user import UserUpdate
from app.services import user_service
from tests.factories import create_company, create_currency, create_user, ensure_role


async def _login(client, name_id: str, password: str = "pw") -> None:
    response = await client.post(
        "/api/auth/login", json={"email": name_id, "password": password}
    )
    assert response.status_code == 200


async def _project_with_pm(client, db_session, *, status: str = "draft"):
    """A project managed by `pm@example.com`, created by a project_admin. Returns
    (project_id, pm_user, admin_user)."""
    admin = await create_user(
        db_session, name_id="admin@example.com", password="pw", role_name="administrator"
    )
    await create_user(
        db_session, name_id="padmin@example.com", password="pw", role_name="project_admin"
    )
    pm = await create_user(
        db_session, name_id="pm@example.com", password="pw", role_name="project_manager"
    )
    vendor = await create_company(db_session, legal_name="Vendor", is_vendor=True)
    customer = await create_company(db_session, legal_name="Customer")
    currency = await create_currency(db_session)
    await _login(client, "padmin@example.com")
    response = await client.post(
        "/api/projects",
        json={
            "name": "Managed",
            "vendor_company_id": str(vendor.id),
            "client_company_id": str(customer.id),
            "invoicing_currency": currency.alpha_code,
            "project_type": "time_and_material",
            "status": status,
            "project_manager_ids": [str(pm.id)],
        },
    )
    assert response.status_code == 201
    # Re-fetched with roles eagerly loaded: the service functions read `user.roles`,
    # which would otherwise lazy-load outside an async-safe context.
    pm = await user_service.get_user_by_id(db_session, pm.id)
    admin = await user_service.get_user_by_id(db_session, admin.id)
    return response.json()["id"], pm, admin


async def _managers_of(client, project_id: str) -> list[str]:
    detail = await client.get(f"/api/projects/{project_id}")
    return [m["id"] for m in detail.json()["project_managers"]]


async def test_deactivating_a_user_removes_them_as_project_manager(
    client, db_session
) -> None:
    project_id, pm, admin = await _project_with_pm(client, db_session)
    assert await _managers_of(client, project_id) == [str(pm.id)]

    # The GET above refreshed this session's copy of the user without its roles.
    pm = await user_service.get_user_by_id(db_session, pm.id)
    await user_service.deactivate_user(db_session, pm, admin)

    assert await _managers_of(client, project_id) == []


async def test_deactivating_a_user_removes_them_from_a_closed_project(
    client, db_session
) -> None:
    project_id, pm, admin = await _project_with_pm(client, db_session, status="closed")

    await user_service.deactivate_user(db_session, pm, admin)

    assert await _managers_of(client, project_id) == []


async def test_removing_project_manager_role_clears_assignments(client, db_session) -> None:
    project_id, pm, admin = await _project_with_pm(client, db_session)
    await ensure_role(db_session, "consultant")

    await user_service.update_user(
        db_session,
        pm,
        UserUpdate(
            full_name=pm.full_name, name_id=pm.name_id, is_sso=False, roles=["consultant"]
        ),
        admin,
    )

    assert await _managers_of(client, project_id) == []


async def test_trigger_clears_project_managers_when_is_active_flips(
    client, db_session
) -> None:
    project_id, pm, _admin = await _project_with_pm(client, db_session)

    # Bypasses the service layer entirely: the DB itself must keep the invariant.
    await db_session.execute(
        text("UPDATE users SET is_active = false WHERE id = :id"), {"id": pm.id}
    )
    await db_session.commit()

    assert await _managers_of(client, project_id) == []


async def test_trigger_rejects_inactive_user_as_project_manager(
    client, db_session
) -> None:
    project_id, _pm, _admin = await _project_with_pm(client, db_session)
    ghost = await create_user(
        db_session, name_id="ghost@example.com", password="pw", role_name="project_manager"
    )
    ghost.is_active = False
    await db_session.commit()

    with pytest.raises(DBAPIError):
        await db_session.execute(
            project_manager_assignments.insert().values(
                project_id=project_id, user_id=ghost.id
            )
        )
    await db_session.rollback()


async def _service_line_with_consultant(client, db_session):
    """padmin-created project + one service line holding `c@example.com`."""
    await create_user(
        db_session, name_id="padmin@example.com", password="pw", role_name="project_admin"
    )
    consultant = await create_user(
        db_session, name_id="c@example.com", password="pw", role_name="consultant"
    )
    pm = await create_user(
        db_session, name_id="pm@example.com", password="pw", role_name="project_manager"
    )
    vendor = await create_company(db_session, legal_name="Vendor", is_vendor=True)
    customer = await create_company(db_session, legal_name="Customer")
    currency = await create_currency(db_session)
    await _login(client, "padmin@example.com")
    project = await client.post(
        "/api/projects",
        json={
            "name": "P",
            "vendor_company_id": str(vendor.id),
            "client_company_id": str(customer.id),
            "invoicing_currency": currency.alpha_code,
            "project_type": "time_and_material",
            "status": "active",
            "project_manager_ids": [str(pm.id)],
        },
    )
    project_id = project.json()["id"]
    line = await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "name": "Line",
            "quantity": "10",
            "uom": "hours",
            "unit_price": "100",
            "user_ids": [str(consultant.id)],
        },
    )
    assert line.status_code == 201
    return project_id, line.json()["id"], consultant


async def _delete_user(db_session, user) -> None:
    user.is_active = False
    await db_session.commit()


async def test_deleted_consultant_stays_on_line_flagged_inactive(client, db_session) -> None:
    project_id, _line_id, consultant = await _service_line_with_consultant(client, db_session)
    await _delete_user(db_session, consultant)

    detail = (await client.get(f"/api/projects/{project_id}")).json()
    users = detail["service_lines"][0]["users"]
    assert users == [
        {"id": str(consultant.id), "full_name": consultant.full_name, "is_active": False}
    ]


async def test_saving_a_line_with_a_deleted_consultant_is_rejected(client, db_session) -> None:
    project_id, line_id, consultant = await _service_line_with_consultant(client, db_session)
    await _delete_user(db_session, consultant)

    body = {
        "name": "Line",
        "quantity": "10",
        "uom": "hours",
        "unit_price": "100",
        "user_ids": [str(consultant.id)],
    }
    rejected = await client.patch(
        f"/api/projects/{project_id}/service-lines/{line_id}", json=body
    )
    assert rejected.status_code == 422
    assert "no longer exists" in rejected.json()["detail"]

    # Removing them is the one thing that works.
    fixed = await client.patch(
        f"/api/projects/{project_id}/service-lines/{line_id}", json={**body, "user_ids": []}
    )
    assert fixed.status_code == 200
    assert fixed.json()["users"] == []


async def test_project_duplicate_drops_deleted_consultants(client, db_session) -> None:
    project_id, _line_id, consultant = await _service_line_with_consultant(client, db_session)
    other = await create_user(
        db_session, name_id="other@example.com", password="pw", role_name="consultant"
    )
    await client.post(
        f"/api/projects/{project_id}/service-lines",
        json={
            "name": "Second",
            "quantity": "1",
            "uom": "hours",
            "unit_price": "1",
            "user_ids": [str(consultant.id), str(other.id)],
        },
    )
    await _delete_user(db_session, consultant)

    duplicate = await client.post(f"/api/projects/{project_id}/duplicate")
    assert duplicate.status_code == 200
    lines = {line["name"]: line for line in duplicate.json()["service_lines"]}
    assert lines["Line"]["users"] == []
    assert [u["id"] for u in lines["Second"]["users"]] == [str(other.id)]


async def test_deleted_consultant_cannot_get_new_hours_but_can_still_be_locked(
    client, db_session
) -> None:
    _project_id, line_id, consultant = await _service_line_with_consultant(client, db_session)
    await _login(client, "c@example.com")
    ok = await client.put(
        "/api/time-entries",
        json=[{"service_line_id": line_id, "date": "2026-08-05", "hours": "3"}],
    )
    assert ok.status_code == 200
    await _delete_user(db_session, consultant)

    await _login(client, "pm@example.com")
    # A PM writing hours on the deleted consultant's behalf is rejected...
    blocked = await client.put(
        "/api/time-entries",
        json=[
            {
                "service_line_id": line_id,
                "date": "2026-08-06",
                "hours": "2",
                "user_id": str(consultant.id),
            }
        ],
    )
    assert blocked.status_code == 207
    assert blocked.json()[0]["error"] == "not_eligible"

    # ...but validating (locking) their existing timesheet still works.
    lock = await client.put(
        "/api/time-entries/lock",
        json={
            "user_id": str(consultant.id),
            "service_line_id": line_id,
            "start_date": "2026-08-05",
            "end_date": "2026-08-05",
            "locked": True,
        },
    )
    assert lock.status_code == 200
    assert lock.json()[0]["is_locked"] is True
