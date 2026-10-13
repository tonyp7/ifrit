import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models.project import BillingMilestone
from tests.factories import create_company, create_currency, create_user


async def _login(client, db_session, role_name: str = "manager") -> None:
    email = f"{role_name}@example.com"
    await create_user(db_session, name_id=email, password="pw", role_name=role_name)
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": "pw"}
    )
    assert response.status_code == 200


async def _create_project(
    client,
    db_session,
    *,
    project_type: str = "fixed_price",
    status: str = "draft",
    alpha_code: str = "EUR",
    numeric_code: str = "978",
    minor_unit: int | None = 2,
) -> dict:
    vendor = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    client_company = await create_company(db_session, legal_name="Beta Client")
    await create_currency(
        db_session,
        alpha_code=alpha_code,
        numeric_code=numeric_code,
        minor_unit=minor_unit,
    )
    payload = {
        "name": "Acme ERP Rollout",
        "vendor_company_id": str(vendor.id),
        "client_company_id": str(client_company.id),
        "invoicing_currency": alpha_code,
        "project_type": project_type,
        "status": status,
    }
    response = await client.post("/api/projects", json=payload)
    assert response.status_code == 201
    return response.json()


def _write_payload(project: dict, **overrides) -> dict:
    """The project form's full PATCH body for `project`, with `overrides` applied."""
    payload = {
        "name": project["name"],
        "vendor_company_id": project["vendor_company_id"],
        "client_company_id": project["client_company_id"],
        "invoicing_currency": project["invoicing_currency"],
        "project_type": project["project_type"],
        "status": project["status"],
        "project_manager_ids": [],
    }
    payload.update(overrides)
    return payload


async def _add(client, project_id: str, description: str, value: str, **extra):
    return await client.post(
        f"/api/projects/{project_id}/billing-milestones",
        json={"description": description, "value": value, **extra},
    )


async def _milestones(client, project_id: str) -> list[dict]:
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    return response.json()["billing_milestones"]


# --- Access ---------------------------------------------------------------------------


async def test_requires_a_session(client, db_session) -> None:
    response = await _add(client, str(uuid.uuid4()), "Kick-off", "100")
    assert response.status_code == 401


async def test_rejects_a_consultant(client, db_session) -> None:
    await _login(client, db_session, role_name="consultant")
    response = await _add(client, str(uuid.uuid4()), "Kick-off", "100")
    assert response.status_code == 403


# --- Create, read, validation -----------------------------------------------------------


async def test_milestones_are_appended_and_listed_in_order(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    for description in ("Kick-off", "Delivery", "Acceptance"):
        response = await _add(client, project["id"], description, "1000.00")
        assert response.status_code == 201

    milestones = await _milestones(client, project["id"])
    assert [m["description"] for m in milestones] == [
        "Kick-off",
        "Delivery",
        "Acceptance",
    ]
    assert [m["position"] for m in milestones] == [0, 1, 2]


async def test_due_date_is_optional_and_round_trips_as_a_plain_date(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    without = await _add(client, project["id"], "Kick-off", "100")
    with_date = await _add(
        client, project["id"], "Delivery", "100", due_date="2027-01-15"
    )

    assert without.json()["due_date"] is None
    assert with_date.json()["due_date"] == "2027-01-15"
    assert [m["due_date"] for m in await _milestones(client, project["id"])] == [
        None,
        "2027-01-15",
    ]


async def test_rejects_a_blank_description(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(client, project["id"], "   ", "100")

    assert response.status_code == 422


async def test_rejects_a_negative_value(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(client, project["id"], "Kick-off", "-1")

    assert response.status_code == 422


async def test_value_decimals_follow_the_currency(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(
        client, db_session, alpha_code="JPY", numeric_code="392", minor_unit=0
    )

    assert (await _add(client, project["id"], "Kick-off", "100.5")).status_code == 422
    # Trailing zeros are not extra precision.
    assert (await _add(client, project["id"], "Kick-off", "100.00")).status_code == 201


async def test_currency_without_minor_unit_allows_two_decimals(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(
        client, db_session, alpha_code="XAU", numeric_code="959", minor_unit=None
    )

    assert (await _add(client, project["id"], "Kick-off", "10.555")).status_code == 422
    assert (await _add(client, project["id"], "Kick-off", "10.55")).status_code == 201


async def test_refused_on_a_project_that_is_not_fixed_price(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(
        client, db_session, project_type="time_and_material"
    )

    response = await _add(client, project["id"], "Kick-off", "100")

    assert response.status_code == 409
    assert await _milestones(client, project["id"]) == []


async def test_refused_on_a_closed_project(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    milestone = (await _add(client, project["id"], "Kick-off", "100")).json()
    await client.patch(
        f"/api/projects/{project['id']}", json=_write_payload(project, status="closed")
    )

    add = await _add(client, project["id"], "Delivery", "100")
    edit = await client.patch(
        f"/api/projects/{project['id']}/billing-milestones/{milestone['id']}",
        json={"description": "Changed", "value": "100"},
    )
    delete = await client.delete(
        f"/api/projects/{project['id']}/billing-milestones/{milestone['id']}"
    )
    reorder = await client.patch(
        f"/api/projects/{project['id']}/billing-milestones/order",
        json={"ids": [milestone["id"]]},
    )

    assert [r.status_code for r in (add, edit, delete, reorder)] == [409] * 4


# --- Update and delete ------------------------------------------------------------------


async def test_update_changes_fields_and_can_clear_the_due_date(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    milestone = (
        await _add(client, project["id"], "Kick-off", "100", due_date="2027-01-15")
    ).json()

    response = await client.patch(
        f"/api/projects/{project['id']}/billing-milestones/{milestone['id']}",
        json={"description": "Kick-off (30%)", "value": "2500.50", "due_date": None},
    )

    assert response.status_code == 200
    (stored,) = await _milestones(client, project["id"])
    assert stored["description"] == "Kick-off (30%)"
    assert Decimal(stored["value"]) == Decimal("2500.50")
    assert stored["due_date"] is None


async def test_milestone_of_another_project_is_not_found(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    milestone = (await _add(client, project["id"], "Kick-off", "100")).json()

    response = await client.patch(
        f"/api/projects/{uuid.uuid4()}/billing-milestones/{milestone['id']}",
        json={"description": "Changed", "value": "100"},
    )
    unknown = await client.delete(
        f"/api/projects/{project['id']}/billing-milestones/{uuid.uuid4()}"
    )

    assert response.status_code == 404
    assert unknown.status_code == 404


async def test_delete_removes_the_row_and_keeps_the_others_in_order(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ids = [
        (await _add(client, project["id"], d, "100")).json()["id"]
        for d in ("Kick-off", "Delivery", "Acceptance")
    ]

    response = await client.delete(
        f"/api/projects/{project['id']}/billing-milestones/{ids[1]}"
    )

    assert response.status_code == 204
    rows = (
        await db_session.execute(
            select(BillingMilestone.id).where(BillingMilestone.id == uuid.UUID(ids[1]))
        )
    ).all()
    assert rows == []
    assert [m["description"] for m in await _milestones(client, project["id"])] == [
        "Kick-off",
        "Acceptance",
    ]


# --- Reorder ----------------------------------------------------------------------------


async def test_reorder_saves_the_new_order(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ids = [
        (await _add(client, project["id"], d, "100")).json()["id"]
        for d in ("Kick-off", "Delivery", "Acceptance")
    ]

    # Also proves the literal "order" segment reaches the reorder handler rather than
    # being taken for a milestone id (which would answer 422).
    response = await client.patch(
        f"/api/projects/{project['id']}/billing-milestones/order",
        json={"ids": [ids[2], ids[0], ids[1]]},
    )

    assert response.status_code == 200
    assert [m["id"] for m in response.json()] == [ids[2], ids[0], ids[1]]
    assert [m["description"] for m in await _milestones(client, project["id"])] == [
        "Acceptance",
        "Kick-off",
        "Delivery",
    ]


async def test_new_milestone_goes_last_after_a_reorder(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ids = [
        (await _add(client, project["id"], d, "100")).json()["id"]
        for d in ("Kick-off", "Delivery")
    ]
    await client.patch(
        f"/api/projects/{project['id']}/billing-milestones/order",
        json={"ids": [ids[1], ids[0]]},
    )

    await _add(client, project["id"], "Acceptance", "100")

    assert [m["description"] for m in await _milestones(client, project["id"])] == [
        "Delivery",
        "Kick-off",
        "Acceptance",
    ]


async def test_stale_reorder_is_refused_and_changes_nothing(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ids = [
        (await _add(client, project["id"], d, "100")).json()["id"]
        for d in ("Kick-off", "Delivery", "Acceptance")
    ]
    url = f"/api/projects/{project['id']}/billing-milestones/order"

    missing = await client.patch(url, json={"ids": [ids[2], ids[1]]})
    duplicated = await client.patch(url, json={"ids": [ids[2], ids[2], ids[1]]})
    foreign = await client.patch(url, json={"ids": [ids[2], ids[1], str(uuid.uuid4())]})

    assert [r.status_code for r in (missing, duplicated, foreign)] == [409] * 3
    assert [m["description"] for m in await _milestones(client, project["id"])] == [
        "Kick-off",
        "Delivery",
        "Acceptance",
    ]


# --- Effects of project updates ---------------------------------------------------------


async def test_changing_the_type_away_from_fixed_price_deletes_milestones(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    for d in ("Kick-off", "Delivery", "Acceptance"):
        await _add(client, project["id"], d, "100")

    response = await client.patch(
        f"/api/projects/{project['id']}",
        json=_write_payload(project, project_type="time_and_material"),
    )

    assert response.status_code == 200
    assert response.json()["project_type"] == "time_and_material"
    assert response.json()["billing_milestones"] == []
    count = (
        await db_session.execute(
            select(BillingMilestone.id).where(
                BillingMilestone.project_id == uuid.UUID(project["id"])
            )
        )
    ).all()
    assert count == []


async def test_saving_without_a_type_change_keeps_milestones(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "Kick-off", "100")

    response = await client.patch(
        f"/api/projects/{project['id']}",
        json=_write_payload(project, name="Renamed"),
    )

    assert response.status_code == 200
    assert len(response.json()["billing_milestones"]) == 1


async def test_rejected_type_change_keeps_milestones(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "Kick-off", "100")

    response = await client.patch(
        f"/api/projects/{project['id']}",
        json=_write_payload(
            project,
            project_type="time_and_material",
            vendor_company_id=str(uuid.uuid4()),
        ),
    )

    assert response.status_code == 422
    detail = (await client.get(f"/api/projects/{project['id']}")).json()
    assert detail["project_type"] == "fixed_price"
    assert len(detail["billing_milestones"]) == 1


async def test_currency_change_keeps_stored_values(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "Kick-off", "100.50")
    await create_currency(
        db_session, alpha_code="JPY", numeric_code="392", minor_unit=0
    )

    response = await client.patch(
        f"/api/projects/{project['id']}",
        json=_write_payload(project, invoicing_currency="JPY"),
    )

    assert response.status_code == 200
    (milestone,) = response.json()["billing_milestones"]
    assert Decimal(milestone["value"]) == Decimal("100.50")


async def test_duplicating_a_project_copies_its_milestones(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    first = (
        await _add(client, project["id"], "Kick-off", "100", due_date="2027-01-15")
    ).json()
    second = (await _add(client, project["id"], "Delivery", "200")).json()
    await client.patch(
        f"/api/projects/{project['id']}/billing-milestones/order",
        json={"ids": [second["id"], first["id"]]},
    )

    copy = (await client.post(f"/api/projects/{project['id']}/duplicate")).json()

    copied = copy["billing_milestones"]
    assert [(m["description"], m["due_date"], Decimal(m["value"])) for m in copied] == [
        ("Delivery", None, Decimal(200)),
        ("Kick-off", "2027-01-15", Decimal(100)),
    ]
    assert {m["id"] for m in copied}.isdisjoint({first["id"], second["id"]})

    await client.patch(
        f"/api/projects/{copy['id']}/billing-milestones/{copied[0]['id']}",
        json={"description": "Changed", "value": "1"},
    )
    source = await _milestones(client, project["id"])
    assert [m["description"] for m in source] == ["Delivery", "Kick-off"]
