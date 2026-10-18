import importlib.util
import uuid
from pathlib import Path
from typing import Any, get_args

from sqlalchemy import CheckConstraint, Table, select

from app.models.project import ProjectReference, ReferenceKind
from tests.factories import create_company, create_currency, create_user

BACKEND_DIR = Path(__file__).resolve().parent.parent


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
    project_type: str = "time_and_material",
    status: str = "draft",
) -> dict[str, Any]:
    vendor = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    client_company = await create_company(db_session, legal_name="Beta Client")
    await create_currency(
        db_session, alpha_code="EUR", numeric_code="978", minor_unit=2
    )
    payload = {
        "name": "Acme ERP Rollout",
        "vendor_company_id": str(vendor.id),
        "client_company_id": str(client_company.id),
        "invoicing_currency": "EUR",
        "project_type": project_type,
        "status": status,
    }
    response = await client.post("/api/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _write_payload(project: dict[str, Any], **overrides) -> dict[str, Any]:
    """The project form's full PATCH body for `project`, with `overrides` applied."""
    payload: dict[str, Any] = {
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


async def _add(client, project_id: str, kind: str, value: str, label=None):
    return await client.post(
        f"/api/projects/{project_id}/project-references",
        json={"kind": kind, "label": label, "value": value},
    )


async def _references(client, project_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    return response.json()["project_references"]


def _shape(
    references: list[dict[str, Any]],
) -> list[tuple[str, str | None, str]]:
    return [(r["kind"], r["label"], r["value"]) for r in references]


# --- Access ---------------------------------------------------------------------------


async def test_a_consultant_cannot_add_a_reference(client, db_session) -> None:
    await _login(client, db_session, "manager")
    project = await _create_project(client, db_session)
    await client.post("/api/auth/logout")
    await _login(client, db_session, "consultant")

    response = await _add(client, project["id"], "purchase_order", "PO-1")

    assert response.status_code == 403


async def test_no_session_is_refused(client, db_session) -> None:
    response = await _add(client, str(uuid.uuid4()), "purchase_order", "PO-1")

    assert response.status_code == 401


# --- Entity and kinds -----------------------------------------------------------------


async def test_a_new_project_has_no_references(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    assert project["project_references"] == []


async def test_references_are_appended_in_order_with_positions(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    first = await _add(client, project["id"], "purchase_order", "PO-1")
    second = await _add(client, project["id"], "purchase_order", "PO-2")
    third = await _add(client, project["id"], "contract", "C-1")

    assert first.status_code == 201
    assert [
        first.json()["position"],
        second.json()["position"],
        third.json()["position"],
    ] == [
        0,
        1,
        2,
    ]
    assert _shape(await _references(client, project["id"])) == [
        ("purchase_order", None, "PO-1"),
        ("purchase_order", None, "PO-2"),
        ("contract", None, "C-1"),
    ]


async def test_a_custom_reference_carries_its_label(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(
        client, project["id"], "custom", "FW-2026-017", "Framework agreement"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["label"] == "Framework agreement"
    assert body["value"] == "FW-2026-017"
    assert body["project_id"] == project["id"]


async def test_every_kind_is_accepted_and_only_these_names_come_back(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    kinds = get_args(ReferenceKind)

    for kind in kinds:
        response = await _add(
            client,
            project["id"],
            kind,
            f"value-{kind}",
            "Label" if kind == "custom" else None,
        )
        assert response.status_code == 201, kind

    assert [r["kind"] for r in await _references(client, project["id"])] == list(kinds)
    assert set(kinds) == {
        "purchase_order",
        "sales_order",
        "contract",
        "buyer_reference",
        "accounting_reference",
        "project_reference",
        "document_reference",
        "custom",
    }


async def test_references_exist_on_every_project_type(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session, project_type="capped_tm")

    response = await _add(client, project["id"], "purchase_order", "PO-1")

    assert response.status_code == 201


def test_the_kind_list_matches_the_migration() -> None:
    path = (
        BACKEND_DIR
        / "alembic"
        / "versions"
        / "0002_manager_role_billing_milestones_project_references_payee_accounts.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0002", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert tuple(module._REFERENCE_KINDS) == get_args(ReferenceKind)
    table = ProjectReference.__table__
    assert isinstance(table, Table)
    check = next(c for c in table.constraints if c.name == "ck_project_references_kind")
    assert isinstance(check, CheckConstraint)
    for kind in get_args(ReferenceKind):
        assert f"'{kind}'" in str(check.sqltext)


# --- Validation -----------------------------------------------------------------------


async def test_blank_value_is_rejected(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(client, project["id"], "purchase_order", "   ")

    assert response.status_code == 422


async def test_value_is_trimmed(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(client, project["id"], "purchase_order", "  PO-17  ")

    assert response.json()["value"] == "PO-17"


async def test_value_longest_allowed_and_one_over(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    assert (
        await _add(client, project["id"], "purchase_order", "x" * 256)
    ).status_code == 422
    assert (
        await _add(client, project["id"], "purchase_order", "x" * 255)
    ).status_code == 201


async def test_custom_without_a_label_is_rejected(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    for label in (None, "", "   "):
        response = await _add(client, project["id"], "custom", "FW-1", label)
        assert response.status_code == 422, label


async def test_custom_label_is_trimmed_and_capped(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    trimmed = await _add(client, project["id"], "custom", "FW-1", "  Framework  ")
    too_long = await _add(client, project["id"], "custom", "FW-2", "x" * 101)

    assert trimmed.json()["label"] == "Framework"
    assert too_long.status_code == 422


async def test_label_on_a_typed_kind_is_rejected(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(client, project["id"], "contract", "C-1", "My contract")

    assert response.status_code == 422


async def test_unknown_kind_is_rejected(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _add(client, project["id"], "OrderReference", "PO-1")

    assert response.status_code == 422


async def test_same_kind_and_value_twice_is_rejected(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "4500123456")

    response = await _add(client, project["id"], "purchase_order", "4500123456")

    assert response.status_code == 422
    assert len(await _references(client, project["id"])) == 1


async def test_values_differing_only_by_case_are_duplicates(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-17")

    response = await _add(client, project["id"], "purchase_order", "po-17")

    assert response.status_code == 422


async def test_labels_differing_only_by_case_are_duplicates(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "custom", "X-1", "Cost Center")

    response = await _add(client, project["id"], "custom", "x-1", "cost center")

    assert response.status_code == 422


async def test_same_value_under_different_kinds_or_labels_is_fine(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    for kind, label in [
        ("purchase_order", None),
        ("contract", None),
        ("custom", "Cost center"),
        ("custom", "Department"),
    ]:
        response = await _add(client, project["id"], kind, "4500123456", label)
        assert response.status_code == 201, (kind, label)


async def test_the_limit_is_fifty(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    for n in range(50):
        response = await _add(client, project["id"], "purchase_order", f"PO-{n}")
        assert response.status_code == 201

    over = await _add(client, project["id"], "purchase_order", "PO-50")

    assert over.status_code == 422
    assert len(await _references(client, project["id"])) == 50


async def test_a_rejected_write_changes_nothing(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-1")

    await _add(client, project["id"], "contract", "   ")
    await _add(client, project["id"], "purchase_order", "po-1")

    assert _shape(await _references(client, project["id"])) == [
        ("purchase_order", None, "PO-1")
    ]


# --- Edit -----------------------------------------------------------------------------


async def _patch(client, project_id: str, reference_id: str, kind, value, label=None):
    return await client.patch(
        f"/api/projects/{project_id}/project-references/{reference_id}",
        json={"kind": kind, "label": label, "value": value},
    )


async def test_edit_changes_the_values_and_keeps_the_position(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-1")
    second = (await _add(client, project["id"], "purchase_order", "PO-2")).json()
    await _add(client, project["id"], "contract", "C-1")

    response = await _patch(client, project["id"], second["id"], "sales_order", "S-9")

    assert response.status_code == 200
    assert response.json()["position"] == 1
    assert _shape(await _references(client, project["id"])) == [
        ("purchase_order", None, "PO-1"),
        ("sales_order", None, "S-9"),
        ("contract", None, "C-1"),
    ]


async def test_edit_to_its_own_values_is_accepted(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ref = (await _add(client, project["id"], "purchase_order", "PO-1")).json()

    response = await _patch(client, project["id"], ref["id"], "purchase_order", "PO-1")

    assert response.status_code == 200


async def test_edit_to_a_value_that_exists_is_rejected(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-1")
    second = (await _add(client, project["id"], "purchase_order", "PO-2")).json()

    response = await _patch(
        client, project["id"], second["id"], "purchase_order", "po-1"
    )

    assert response.status_code == 422
    assert second["value"] == (await _references(client, project["id"]))[1]["value"]


async def test_edit_between_typed_and_custom(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ref = (await _add(client, project["id"], "contract", "C-1")).json()

    to_custom = await _patch(
        client, project["id"], ref["id"], "custom", "C-1", "Master agreement"
    )
    label_less = await _patch(client, project["id"], ref["id"], "custom", "C-1")
    back = await _patch(client, project["id"], ref["id"], "contract", "C-1")

    assert to_custom.json()["label"] == "Master agreement"
    assert label_less.status_code == 422
    assert back.json()["label"] is None


async def test_another_projects_reference_is_not_found(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    other = await client.post(
        "/api/projects",
        json={
            "name": "Other",
            "vendor_company_id": project["vendor_company_id"],
            "client_company_id": project["client_company_id"],
            "invoicing_currency": "EUR",
            "project_type": "time_and_material",
        },
    )
    ref = (await _add(client, other.json()["id"], "purchase_order", "PO-1")).json()

    edited = await _patch(client, project["id"], ref["id"], "purchase_order", "PO-2")
    deleted = await client.delete(
        f"/api/projects/{project['id']}/project-references/{ref['id']}"
    )

    assert edited.status_code == 404
    assert deleted.status_code == 404
    assert len(await _references(client, other.json()["id"])) == 1


# --- Delete ---------------------------------------------------------------------------


async def test_delete_removes_the_row_for_good(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    keep = (await _add(client, project["id"], "purchase_order", "PO-1")).json()
    gone = (await _add(client, project["id"], "contract", "C-1")).json()

    response = await client.delete(
        f"/api/projects/{project['id']}/project-references/{gone['id']}"
    )

    assert response.status_code == 204
    assert [r["id"] for r in await _references(client, project["id"])] == [keep["id"]]
    rows = (await db_session.execute(select(ProjectReference))).scalars().all()
    assert [r.id for r in rows] == [uuid.UUID(keep["id"])]


async def test_a_deleted_value_can_be_added_again(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    ref = (await _add(client, project["id"], "purchase_order", "PO-1")).json()
    await client.delete(f"/api/projects/{project['id']}/project-references/{ref['id']}")

    response = await _add(client, project["id"], "purchase_order", "PO-1")

    assert response.status_code == 201


# --- Reorder --------------------------------------------------------------------------


async def _reorder(client, project_id: str, ids: list[str]):
    return await client.patch(
        f"/api/projects/{project_id}/project-references/order", json={"ids": ids}
    )


async def test_reorder_saves_the_new_order(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    a = (await _add(client, project["id"], "purchase_order", "A")).json()
    b = (await _add(client, project["id"], "purchase_order", "B")).json()
    c = (await _add(client, project["id"], "purchase_order", "C")).json()

    response = await _reorder(client, project["id"], [c["id"], a["id"], b["id"]])

    assert response.status_code == 200
    assert [r["value"] for r in response.json()] == ["C", "A", "B"]
    assert [r["position"] for r in response.json()] == [0, 1, 2]
    assert [r["value"] for r in await _references(client, project["id"])] == [
        "C",
        "A",
        "B",
    ]


async def test_a_new_reference_goes_after_a_reorder(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    a = (await _add(client, project["id"], "purchase_order", "A")).json()
    b = (await _add(client, project["id"], "purchase_order", "B")).json()
    await _reorder(client, project["id"], [b["id"], a["id"]])

    await _add(client, project["id"], "purchase_order", "C")

    assert [r["value"] for r in await _references(client, project["id"])] == [
        "B",
        "A",
        "C",
    ]


async def test_a_stale_reorder_is_a_conflict_and_changes_nothing(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    a = (await _add(client, project["id"], "purchase_order", "A")).json()
    b = (await _add(client, project["id"], "purchase_order", "B")).json()
    await _add(client, project["id"], "purchase_order", "C")

    missing = await _reorder(client, project["id"], [b["id"], a["id"]])
    extra = await _reorder(
        client, project["id"], [b["id"], a["id"], str(uuid.uuid4()), str(uuid.uuid4())]
    )
    repeated = await _reorder(client, project["id"], [a["id"], a["id"], b["id"]])

    assert (missing.status_code, extra.status_code, repeated.status_code) == (
        409,
        409,
        409,
    )
    assert [r["value"] for r in await _references(client, project["id"])] == [
        "A",
        "B",
        "C",
    ]


async def test_the_order_route_is_not_taken_for_a_reference_id(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)

    response = await _reorder(client, project["id"], [])

    # An empty project has an empty list, which matches: it reached the reorder handler,
    # not the single-reference route (which would answer 422 for "order" as a UUID).
    assert response.status_code == 200
    assert response.json() == []


# --- Closed projects ------------------------------------------------------------------


async def _closed_project_with_references(client, db_session):
    project = await _create_project(client, db_session)
    a = (await _add(client, project["id"], "purchase_order", "PO-1")).json()
    b = (await _add(client, project["id"], "contract", "C-1")).json()
    closed = await client.patch(
        f"/api/projects/{project['id']}", json=_write_payload(project, status="closed")
    )
    assert closed.status_code == 200
    return project, a, b


async def test_every_write_is_a_conflict_on_a_closed_project(
    client, db_session
) -> None:
    await _login(client, db_session)
    project, a, b = await _closed_project_with_references(client, db_session)

    add = await _add(client, project["id"], "purchase_order", "PO-2")
    edit = await _patch(client, project["id"], a["id"], "purchase_order", "PO-9")
    delete = await client.delete(
        f"/api/projects/{project['id']}/project-references/{a['id']}"
    )
    reorder = await _reorder(client, project["id"], [b["id"], a["id"]])

    assert (
        add.status_code,
        edit.status_code,
        delete.status_code,
        reorder.status_code,
    ) == (
        409,
        409,
        409,
        409,
    )
    assert [r["value"] for r in await _references(client, project["id"])] == [
        "PO-1",
        "C-1",
    ]


async def test_reopening_makes_them_editable_again(client, db_session) -> None:
    await _login(client, db_session)
    project, _, _ = await _closed_project_with_references(client, db_session)
    reopened = await client.patch(
        f"/api/projects/{project['id']}", json=_write_payload(project, status="active")
    )
    assert reopened.status_code == 200

    response = await _add(client, project["id"], "purchase_order", "PO-2")

    assert response.status_code == 201


# --- Not part of the project's own save, and Duplicate --------------------------------


async def test_saving_the_project_leaves_its_references_alone(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-1")

    response = await client.patch(
        f"/api/projects/{project['id']}",
        json=_write_payload(
            project,
            name="Renamed",
            project_references=[
                {"kind": "contract", "label": None, "value": "IGNORED"}
            ],
        ),
    )

    assert response.status_code == 200
    assert _shape(response.json()["project_references"]) == [
        ("purchase_order", None, "PO-1")
    ]


async def test_duplicating_copies_the_references_in_order(client, db_session) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-2")
    await _add(client, project["id"], "custom", "FW-1", "Framework agreement")
    await _add(client, project["id"], "purchase_order", "PO-1")

    response = await client.post(f"/api/projects/{project['id']}/duplicate")

    assert response.status_code == 200
    copy = response.json()
    assert copy["id"] != project["id"]
    assert _shape(copy["project_references"]) == _shape(
        await _references(client, project["id"])
    )


async def test_editing_the_copys_references_leaves_the_original(
    client, db_session
) -> None:
    await _login(client, db_session)
    project = await _create_project(client, db_session)
    await _add(client, project["id"], "purchase_order", "PO-1")
    copy = (await client.post(f"/api/projects/{project['id']}/duplicate")).json()

    response = await client.delete(
        f"/api/projects/{copy['id']}/project-references/"
        f"{copy['project_references'][0]['id']}"
    )

    assert response.status_code == 204
    assert _shape(await _references(client, project["id"])) == [
        ("purchase_order", None, "PO-1")
    ]


async def test_a_closed_project_can_be_duplicated_with_its_references(
    client, db_session
) -> None:
    await _login(client, db_session)
    project, _, _ = await _closed_project_with_references(client, db_session)

    copy = (await client.post(f"/api/projects/{project['id']}/duplicate")).json()

    assert copy["status"] == "draft"
    assert _shape(copy["project_references"]) == [
        ("purchase_order", None, "PO-1"),
        ("contract", None, "C-1"),
    ]
