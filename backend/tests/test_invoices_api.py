import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.models.company import Address, Company, PayeeAccount
from app.models.invoice import Invoice, InvoiceLine, InvoiceReference
from app.models.project import Project, ProjectReference
from app.services.invoice_service import money_round
from tests.factories import create_company
from tests.invoice_helpers import (
    add_milestone,
    add_service_line,
    ensure_currency,
    log_hours,
    login,
    make_consultant,
    make_issued_invoice,
    make_project,
)

URL = "/api/invoices"
PAYEE = {
    "payment_means_code": "58",
    "account_scheme": "iban",
    "account_identifier": "BE71 0961 2345 6769",
    "currency_code": "EUR",
    "bic": "GEBABEBB",
}


def _body(project: Project, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": str(project.id),
        "bill_from": {
            "name": "Ifrit Consulting",
            "address": {
                "line1": "12 Rue de la Paix",
                "city": "Paris",
                "country_code": "FR",
            },
        },
        "bill_to": {"name": "ACME"},
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "lines": [
            {
                "description": "Senior developer",
                "quantity": "10",
                "uom": "hours",
                "unit_price": "95",
            }
        ],
    }
    body.update(overrides)
    return body


async def _create(client, project: Project, **overrides: Any) -> dict[str, Any]:
    response = await client.post(URL, json=_body(project, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def _stored_totals_match(db_session, invoice_id: str) -> None:
    """The stored amounts equal a fresh computation from the stored lines."""
    db_session.expire_all()
    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    lines = (
        (
            await db_session.execute(
                select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
            )
        )
        .scalars()
        .all()
    )
    minor = (await ensure_currency(db_session, invoice.currency_code)).minor_unit
    for line in lines:
        assert line.amount == money_round(line.quantity * line.unit_price, minor)
    assert invoice.subtotal == sum((line.amount for line in lines), Decimal(0))
    assert invoice.total == invoice.subtotal


# --- access ----------------------------------------------------------------------


async def test_no_session_is_401(client) -> None:
    assert (await client.get(URL)).status_code == 401


@pytest.mark.parametrize("role", ["manager", "administrator", "consultant"])
async def test_other_roles_are_403(client, db_session, role) -> None:
    await login(client, db_session, role)
    for response in (
        await client.get(URL),
        await client.get(f"{URL}/projects"),
        await client.post(URL, json={}),
    ):
        assert response.status_code == 403


async def test_billing_reads_project_data_only_through_invoices(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    assert (await client.get(URL)).status_code == 200
    assert (await client.get(f"{URL}/projects/{project.id}")).status_code == 200
    assert (await client.get(f"/api/projects/{project.id}")).status_code == 403


# --- projects for the form -------------------------------------------------------


async def test_picker_lists_only_invoiceable_projects(client, db_session) -> None:
    await login(client, db_session)
    await make_project(db_session, name="Active T&M")
    await make_project(db_session, name="Active capped", project_type="capped_tm")
    await make_project(db_session, name="Draft T&M", status="draft")
    await make_project(db_session, name="Closed T&M", status="closed")
    await make_project(db_session, name="Active fixed", project_type="fixed_price")
    deleted = await make_project(db_session, name="Deleted T&M")
    deleted.is_active = False
    await db_session.commit()

    names = [p["name"] for p in (await client.get(f"{URL}/projects")).json()]
    assert names == ["Active capped", "Active fixed", "Active T&M"]
    searched = (await client.get(f"{URL}/projects", params={"search": "capp"})).json()
    assert [p["name"] for p in searched] == ["Active capped"]


async def test_invoiced_projects_include_closed_ones(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session, name="Billed")
    await make_project(db_session, name="Never billed")
    await _create(client, project)
    project.status = "closed"
    await db_session.commit()

    names = [
        p["name"]
        for p in (await client.get(f"{URL}/projects", params={"invoiced": True})).json()
    ]
    assert names == ["Billed"]


async def test_billing_context(client, db_session) -> None:
    await login(client, db_session)
    await ensure_currency(db_session, "EUR")
    vendor = await create_company(db_session, legal_name="Ifrit SAS", is_vendor=True)
    vendor.trading_name = "Ifrit"
    db_session.add_all(
        [
            Address(
                company_id=vendor.id,
                address_type="registered",
                line1="12 Rue de la Paix",
                city="Paris",
                country_code="FR",
                is_primary=True,
            ),
            PayeeAccount(
                company_id=vendor.id,
                payment_means_code="58",
                account_scheme="iban",
                account_identifier="BE71096123456769",
                currency_code="EUR",
                is_primary=True,
            ),
        ]
    )
    await db_session.commit()
    project = await make_project(db_session, vendor=vendor)
    await add_service_line(db_session, project, name="Active")
    await add_service_line(db_session, project, name="Gone", is_active=False)
    db_session.add(
        ProjectReference(
            project_id=project.id, kind="purchase_order", value="PO-1", position=0
        )
    )
    await db_session.commit()

    body = (await client.get(f"{URL}/projects/{project.id}")).json()

    assert body["vendor"]["display_name"] == "Ifrit"
    assert body["vendor"]["addresses"][0]["address_type"] == "registered"
    assert body["client"]["display_name"] == "ACME Corp"
    assert body["payee_accounts"][0]["account_identifier"] == "BE71096123456769"
    assert [line["name"] for line in body["service_lines"]] == ["Active"]
    assert body["references"] == [
        {"kind": "purchase_order", "label": None, "value": "PO-1"}
    ]
    assert body["currency_minor_unit"] == 2
    assert body["milestones"] == []


async def test_billing_context_lists_fixed_price_milestones_in_order(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session, project_type="fixed_price")
    await add_milestone(db_session, project, "Phase 2", "12000", position=1)
    await add_milestone(
        db_session, project, "Phase 1", "10000", position=0, due_date=date(2026, 11, 1)
    )

    body = (await client.get(f"{URL}/projects/{project.id}")).json()

    assert [
        (m["description"], m["due_date"], Decimal(m["value"]))
        for m in body["milestones"]
    ] == [("Phase 1", "2026-11-01", 10000), ("Phase 2", None, 12000)]


async def test_billing_context_of_a_deleted_project_is_404(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    project.is_active = False
    await db_session.commit()

    assert (await client.get(f"{URL}/projects/{project.id}")).status_code == 404
    assert (await client.get(f"{URL}/projects/{uuid.uuid4()}")).status_code == 404


# --- creating and editing --------------------------------------------------------


async def test_create_a_draft(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    body = await _create(client, project, payment_terms="net_30")

    assert body["status"] == "draft"
    assert body["currency_code"] == "EUR"
    assert body["bill_from"]["address"]["city"] == "Paris"
    assert body["bill_to"] == {"name": "ACME", "address": None}
    assert Decimal(body["subtotal"]) == Decimal("950.00")
    assert body["payment_terms"] == "net_30"
    await _stored_totals_match(db_session, body["id"])


@pytest.mark.parametrize(
    ("status", "project_type"),
    [
        ("closed", "time_and_material"),
        ("draft", "time_and_material"),
        ("closed", "fixed_price"),
    ],
)
async def test_create_for_a_non_invoiceable_project_is_409(
    client, db_session, status, project_type
) -> None:
    await login(client, db_session)
    project = await make_project(db_session, status=status, project_type=project_type)

    response = await client.post(URL, json=_body(project))

    assert response.status_code == 409
    assert (await db_session.execute(select(func.count(Invoice.id)))).scalar_one() == 0


async def test_a_draft_survives_its_project_being_closed(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project)
    project.status = "closed"
    await db_session.commit()

    response = await client.patch(
        f"{URL}/{created['id']}", json=_body(project, bill_to={"name": "ACME Ltd"})
    )

    assert response.status_code == 200
    assert response.json()["bill_to"]["name"] == "ACME Ltd"


async def test_moving_a_draft_to_a_non_invoiceable_project_is_409(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    closed = await make_project(db_session, name="Closed", status="closed")
    created = await _create(client, project)

    response = await client.patch(f"{URL}/{created['id']}", json=_body(closed))

    assert response.status_code == 409


async def test_moving_a_draft_to_another_invoiceable_project(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    other = await make_project(db_session, name="Other", currency="USD")
    created = await _create(client, project)

    body = (await client.patch(f"{URL}/{created['id']}", json=_body(other))).json()

    assert body["project_id"] == str(other.id)
    assert body["currency_code"] == "USD"


async def test_currency_follows_the_project(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project)
    await ensure_currency(db_session, "USD")
    project.invoicing_currency = "USD"
    await db_session.commit()

    body = (await client.patch(f"{URL}/{created['id']}", json=_body(project))).json()

    assert body["currency_code"] == "USD"


async def test_amounts_round_half_away_from_zero(client, db_session) -> None:
    await login(client, db_session)
    eur = await make_project(db_session)
    jpy = await make_project(db_session, name="Yen", currency="JPY")
    days = {
        "description": "Architect",
        "quantity": "1.42857",
        "uom": "days",
        "unit_price": "700",
    }
    yen = {
        "description": "Work",
        "quantity": "2.5",
        "uom": "hours",
        "unit_price": "333",
    }

    eur_body = await _create(client, eur, lines=[days])
    jpy_body = await _create(client, jpy, lines=[yen])

    assert Decimal(eur_body["lines"][0]["amount"]) == Decimal("1000.00")
    assert Decimal(jpy_body["lines"][0]["amount"]) == Decimal(833)
    await _stored_totals_match(db_session, eur_body["id"])
    await _stored_totals_match(db_session, jpy_body["id"])


async def test_a_discount_line_reduces_the_subtotal(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    lines = [
        {"description": "Work", "quantity": "10", "uom": "hours", "unit_price": "95"},
        {
            "description": "Early payment discount",
            "quantity": "1",
            "uom": "ea",
            "unit_price": "-250",
        },
    ]

    body = await _create(client, project, lines=lines)

    assert Decimal(body["subtotal"]) == Decimal("700.00")
    assert Decimal(body["total"]) == Decimal("700.00")


async def test_patch_replaces_lines_and_references_in_order(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(
        client, project, references=[{"kind": "contract", "value": "CT-1"}]
    )
    lines = [
        {"description": f"Line {n}", "quantity": "1", "uom": "ea", "unit_price": str(n)}
        for n in (3, 1, 2)
    ]
    references = [
        {"kind": "purchase_order", "value": "PO-2"},
        {"kind": "custom", "label": "Framework", "value": "FW-1"},
    ]

    body = (
        await client.patch(
            f"{URL}/{created['id']}",
            json=_body(project, lines=lines, references=references),
        )
    ).json()

    assert [line["description"] for line in body["lines"]] == [
        "Line 3",
        "Line 1",
        "Line 2",
    ]
    assert [ref["value"] for ref in body["references"]] == ["PO-2", "FW-1"]
    await _stored_totals_match(db_session, created["id"])
    count = await db_session.execute(select(func.count(InvoiceReference.id)))
    assert count.scalar_one() == 2


async def test_editing_the_draft_never_changes_the_project(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    db_session.add(
        ProjectReference(
            project_id=project.id, kind="contract", value="CT-77", position=0
        )
    )
    await db_session.commit()

    await _create(client, project, references=[{"kind": "contract", "value": "CT-78"}])

    db_session.expire_all()
    stored = (await db_session.execute(select(ProjectReference.value))).scalars().all()
    assert stored == ["CT-77"]


# --- payee details ---------------------------------------------------------------


async def test_payee_details_are_stored_normalized(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    body = await _create(client, project, payee=PAYEE)

    assert body["payee"]["account_identifier"] == "BE71096123456769"
    assert body["payee"]["bic"] == "GEBABEBB"
    assert body["payee"]["bank_address"] is None


async def test_an_invalid_payee_iban_is_422(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    response = await client.post(
        URL,
        json=_body(project, payee={**PAYEE, "account_identifier": "BE71096123456768"}),
    )

    assert response.status_code == 422


async def test_an_unknown_payee_currency_is_422(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    response = await client.post(
        URL, json=_body(project, payee={**PAYEE, "currency_code": "ZZZ"})
    )

    assert response.status_code == 422


async def test_a_disabled_payee_currency_still_saves(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    await ensure_currency(db_session, "SEK", is_enabled=False)

    body = await _create(
        client,
        project,
        payee={**PAYEE, "payment_means_code": "30", "currency_code": "SEK"},
    )

    assert body["payee"]["currency_code"] == "SEK"


async def test_payee_details_survive_the_company_account(client, db_session) -> None:
    await login(client, db_session)
    await ensure_currency(db_session, "EUR")
    vendor = await create_company(db_session, legal_name="Ifrit", is_vendor=True)
    account = PayeeAccount(
        company_id=vendor.id,
        payment_means_code="58",
        account_scheme="iban",
        account_identifier="BE71096123456769",
        currency_code="EUR",
        bic="GEBABEBB",
    )
    db_session.add(account)
    await db_session.commit()
    project = await make_project(db_session, vendor=vendor)
    created = await _create(client, project, payee=PAYEE)

    account.bic = "KREDBEBB"
    await db_session.commit()
    edited = (await client.get(f"{URL}/{created['id']}")).json()
    await db_session.delete(account)
    await db_session.commit()
    deleted = (await client.get(f"{URL}/{created['id']}")).json()

    assert edited["payee"]["bic"] == "GEBABEBB"
    assert deleted["payee"]["account_identifier"] == "BE71096123456769"


# --- delete and duplicate --------------------------------------------------------


async def test_delete_a_draft(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(
        client, project, references=[{"kind": "contract", "value": "C"}]
    )

    assert (await client.delete(f"{URL}/{created['id']}")).status_code == 204
    assert (await client.get(f"{URL}/{created['id']}")).status_code == 404
    for model in (InvoiceLine, InvoiceReference):
        count = await db_session.execute(select(func.count(model.id)))
        assert count.scalar_one() == 0


async def test_an_issued_invoice_cannot_be_changed_or_deleted(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project)
    invoice = await db_session.get(Invoice, uuid.UUID(created["id"]))
    assert invoice is not None
    invoice.status = "issued"
    invoice.number = "INV-2026-0001"
    invoice.invoice_date = date(2026, 10, 14)
    invoice.issued_at = datetime(2026, 10, 14, 9, tzinfo=UTC)
    invoice.currency_minor_unit = 2
    await db_session.commit()

    assert (
        await client.patch(f"{URL}/{created['id']}", json=_body(project))
    ).status_code == 409
    assert (await client.delete(f"{URL}/{created['id']}")).status_code == 409


async def test_duplicate_copies_everything_in_order(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    lines = [
        {"description": f"Line {n}", "quantity": "1", "uom": "ea", "unit_price": str(n)}
        for n in (2, 1, 3)
    ]
    references = [
        {"kind": "purchase_order", "value": "PO-1"},
        {"kind": "contract", "value": "CT-1"},
    ]
    created = await _create(
        client,
        project,
        lines=lines,
        references=references,
        payee=PAYEE,
        due_date="2026-12-01",
    )
    # A closed project still gets the copy: issuing it is what would be refused.
    project.status = "closed"
    await db_session.commit()

    response = await client.post(f"{URL}/{created['id']}/duplicate")

    assert response.status_code == 201
    copy = response.json()
    assert copy["id"] != created["id"]
    assert copy["status"] == "draft"
    for key in (
        "bill_from",
        "bill_to",
        "period_start",
        "period_end",
        "due_date",
        "payee",
    ):
        assert copy[key] == created[key]
    assert [line["description"] for line in copy["lines"]] == [
        "Line 2",
        "Line 1",
        "Line 3",
    ]
    assert [ref["value"] for ref in copy["references"]] == ["PO-1", "CT-1"]
    await _stored_totals_match(db_session, copy["id"])


async def test_a_fixed_price_draft_stores_no_period(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session, project_type="fixed_price")

    created = await _create(client, project)
    patched = await client.patch(f"{URL}/{created['id']}", json=_body(project))

    assert (created["period_start"], created["period_end"]) == (None, None)
    assert patched.json()["period_start"] is None
    # A T&M draft keeps the period it is given.
    tm = await _create(client, await make_project(db_session, name="T&M"))
    assert tm["period_start"] == "2026-09-01"


# --- list ------------------------------------------------------------------------


async def test_list_is_newest_first_and_sortable(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    first = await _create(client, project, bill_to={"name": "Bravo"})
    second = await _create(client, project, bill_to={"name": "Alpha"})

    default = (await client.get(URL)).json()
    by_client = (await client.get(URL, params={"sort_by": "client"})).json()
    unknown = (await client.get(URL, params={"sort_by": "nope"})).json()

    assert [item["id"] for item in default["items"]] == [second["id"], first["id"]]
    assert [item["client_name"] for item in by_client["items"]] == ["Alpha", "Bravo"]
    assert [item["id"] for item in unknown["items"]] == [second["id"], first["id"]]
    assert default["total"] == 2
    assert default["page_size"] == 50


async def test_list_sorts_by_total(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    for price in ("300", "100", "200"):
        await _create(
            client,
            project,
            lines=[
                {"description": "x", "quantity": "1", "uom": "ea", "unit_price": price}
            ],
        )

    body = (
        await client.get(URL, params={"sort_by": "total", "sort_dir": "desc"})
    ).json()

    assert [Decimal(item["total"]) for item in body["items"]] == [300, 200, 100]


async def test_list_filters_by_project(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    other = await make_project(db_session, name="Other")
    await _create(client, project)
    kept = await _create(client, other)

    body = (await client.get(URL, params={"project_id": str(other.id)})).json()

    assert [item["id"] for item in body["items"]] == [kept["id"]]
    assert body["items"][0]["project_name"] == "Other"


async def test_billed_for_falls_back_to_every_line(client, db_session) -> None:
    await login(client, db_session)
    tm = await _create(client, await make_project(db_session))
    project = await make_project(db_session, name="Fixed", project_type="fixed_price")
    line = {"quantity": "1", "uom": "ea", "unit_price": "12000"}
    fixed = await _create(
        client,
        project,
        lines=[
            {"description": "Phase 2 – Delivery of beta", **line},
            {"description": "Travel", **line},
        ],
    )
    empty = await _create(client, project, lines=[])

    items = {i["id"]: i for i in (await client.get(URL)).json()["items"]}

    assert items[fixed["id"]]["period_start"] is None
    assert items[fixed["id"]]["lines_summary"] == "Phase 2 – Delivery of beta, Travel"
    assert items[empty["id"]]["lines_summary"] is None
    assert items[tm["id"]]["period_start"] == "2026-09-01"
    for direction in ("asc", "desc"):
        ordered = (
            await client.get(
                URL, params={"sort_by": "billed_for", "sort_dir": direction}
            )
        ).json()["items"]
        # Invoices without a period come last both ways.
        assert ordered[0]["id"] == tm["id"]


async def test_list_paginates(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    invoice_rows = [
        Invoice(
            project_id=project.id,
            currency_code="EUR",
            bill_from_name="F",
            bill_to_name=f"T{n}",
            subtotal=Decimal(0),
            total=Decimal(0),
        )
        for n in range(51)
    ]
    db_session.add_all(invoice_rows)
    await db_session.commit()

    page2 = (await client.get(URL, params={"page": 2})).json()

    assert page2["total"] == 51
    assert len(page2["items"]) == 1


# --- warnings --------------------------------------------------------------------


def _codes(body: dict[str, Any]) -> set[str]:
    return {warning["code"] for warning in body["warnings"]}


async def test_saved_draft_warnings(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 2), 8)
    await ensure_currency(db_session, "USD")
    zero = [
        {"description": "Licence", "quantity": "0", "uom": "ea", "unit_price": "10"}
    ]

    no_payee = await _create(client, project, lines=zero)
    usd_payee = await _create(
        client,
        project,
        payee={**PAYEE, "payment_means_code": "30", "currency_code": "USD"},
    )

    assert {"unlocked_hours", "zero_quantity", "no_payee_account"} <= _codes(no_payee)
    assert "payee_currency" in _codes(usd_payee)
    assert "no_payee_account" not in _codes(usd_payee)


async def test_unlocked_hours_on_a_saved_draft_cover_every_project_line(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project, name="Not selected")
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 2), 8)

    body = await _create(client, project, payee=PAYEE)

    [unlocked] = [w for w in body["warnings"] if w["code"] == "unlocked_hours"]
    assert unlocked["service_lines"][0]["name"] == "Not selected"


async def test_inactive_company_warning(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project, payee=PAYEE)
    client_company = await db_session.get(Company, project.client_company_id)
    assert client_company is not None
    client_company.is_active = False
    await db_session.commit()

    body = (await client.get(f"{URL}/{created['id']}")).json()

    [inactive] = [w for w in body["warnings"] if w["code"] == "inactive_company"]
    assert inactive["companies"] == ["client"]


# --- issuing and voiding through the API -----------------------------------------


async def _issue(client, invoice_id: str):
    return await client.post(f"{URL}/{invoice_id}/issue")


async def test_issue_and_void_through_the_api(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project, payment_terms="net_30", payee=PAYEE)

    preview = await client.get(f"{URL}/{created['id']}/issue-preview")
    issued = await _issue(client, created["id"])
    voided = await client.post(
        f"{URL}/{created['id']}/void", json={"reason": "  Wrong period "}
    )

    assert preview.status_code == 200
    assert preview.json()["blocking"] == []
    assert issued.status_code == 200
    body = issued.json()
    assert body["status"] == "issued"
    assert body["number"] == preview.json()["number"]
    assert body["invoice_date"] == preview.json()["invoice_date"]
    assert body["due_date"] == preview.json()["due_date"]
    assert body["issued_by_name"]
    assert body["warnings"] == []
    assert voided.status_code == 200
    assert voided.json()["status"] == "void"
    assert voided.json()["void_reason"] == "Wrong period"
    assert voided.json()["number"] == body["number"]


async def test_issue_refusals(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    no_lines = await _create(client, project, lines=[])
    blocked = await _create(client, project)

    lines_response = await _issue(client, no_lines["id"])
    project.status = "closed"
    await db_session.commit()
    project_response = await _issue(client, blocked["id"])

    assert lines_response.status_code == 409
    assert lines_response.json()["detail"] == "An invoice needs at least one line"
    assert project_response.status_code == 409
    assert project_response.json()["detail"] == (
        "This invoice cannot be issued because its project is not Active."
    )
    assert (await _issue(client, str(uuid.uuid4()))).status_code == 404


async def test_void_refusals_and_reason_length(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    draft = await _create(client, project)

    assert (await client.post(f"{URL}/{draft['id']}/void", json={})).status_code == 409
    await _issue(client, draft["id"])
    too_long = await client.post(
        f"{URL}/{draft['id']}/void", json={"reason": "x" * 501}
    )
    assert too_long.status_code == 422
    blank = await client.post(f"{URL}/{draft['id']}/void", json={"reason": "   "})
    assert blank.json()["void_reason"] is None


async def test_issue_preview_is_only_for_drafts(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project)
    await _issue(client, created["id"])

    assert (await client.get(f"{URL}/{created['id']}/issue-preview")).status_code == 409


async def test_issue_routes_require_billing(client, db_session) -> None:
    await login(client, db_session, "manager")
    some_id = uuid.uuid4()
    for response in (
        await client.post(f"{URL}/{some_id}/issue"),
        await client.post(f"{URL}/{some_id}/void", json={}),
        await client.get(f"{URL}/{some_id}/issue-preview"),
    ):
        assert response.status_code == 403


async def test_void_is_hidden_unless_asked_for(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    await make_issued_invoice(db_session, "INV-2026-0001", project=project)
    await make_issued_invoice(
        db_session, "INV-2026-0002", status="void", project=project
    )
    draft = await _create(client, project)

    default = (await client.get(URL)).json()
    with_void = (
        await client.get(
            URL, params=[("status", "draft"), ("status", "issued"), ("status", "void")]
        )
    ).json()
    only_void = (await client.get(URL, params={"status": "void"})).json()

    assert {item["number"] for item in default["items"]} == {"INV-2026-0001", None}
    assert default["total"] == 2
    assert with_void["total"] == 3
    assert [item["number"] for item in only_void["items"]] == ["INV-2026-0002"]
    assert any(item["id"] == draft["id"] for item in default["items"])


async def test_list_sorts_by_number_and_issued(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    await make_issued_invoice(db_session, "INV-2026-0002", project=project)
    await make_issued_invoice(db_session, "INV-2026-0001", project=project)

    by_number = (await client.get(URL, params={"sort_by": "number"})).json()
    by_issued = await client.get(URL, params={"sort_by": "issued", "sort_dir": "desc"})

    assert [item["number"] for item in by_number["items"]] == [
        "INV-2026-0001",
        "INV-2026-0002",
    ]
    assert by_issued.status_code == 200
    assert all(item["issued_at"] for item in by_issued.json()["items"])


async def test_duplicate_an_issued_invoice_through_the_api(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = await _create(client, project, payment_terms="net_30", payee=PAYEE)
    await _issue(client, created["id"])

    copy = (await client.post(f"{URL}/{created['id']}/duplicate")).json()

    assert copy["status"] == "draft"
    assert copy["number"] is None and copy["invoice_date"] is None
    assert copy["payment_terms"] == "net_30" and copy["due_date"] is None
    assert copy["payee"]["account_identifier"] == "BE71096123456769"


# --- list search -----------------------------------------------------------------


def _ids(body: dict[str, Any]) -> list[str]:
    return [item["id"] for item in body["items"]]


async def test_search_matches_the_number_the_project_the_client_and_any_line(
    client, db_session
) -> None:
    await login(client, db_session)
    numbered = await make_issued_invoice(db_session, "2026-0042")
    other_number = await make_issued_invoice(db_session, "2026-0099")
    project = await make_project(db_session, name="Zephyr migration")
    by_project = await _create(client, project)
    by_client = await _create(
        client, await make_project(db_session, name="P2"), bill_to={"name": "Globex SA"}
    )
    line = {"quantity": "1", "uom": "ea", "unit_price": "10"}
    by_line = await _create(
        client,
        await make_project(db_session, name="P3"),
        lines=[
            {"description": "Setup", **line},
            {"description": "Downpayment", **line},
        ],
    )

    async def found(text: str) -> list[str]:
        return _ids((await client.get(URL, params={"search": text})).json())

    assert await found("0042") == [str(numbered.id)]
    assert await found("2026-00") == [str(other_number.id), str(numbered.id)]
    assert await found("zephyr") == [by_project["id"]]
    assert await found("GLOBEX") == [by_client["id"]]
    # The matching line is not the invoice's first.
    assert await found("downpay") == [by_line["id"]]
    assert await found("no such thing") == []


async def test_search_is_not_a_wildcard(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    literal_percent = await _create(client, project, bill_to={"name": "50% Corp"})
    await _create(client, project, bill_to={"name": "500 Corp"})
    underscore = await _create(client, project, bill_to={"name": "Foo_Bar"})
    await _create(client, project, bill_to={"name": "FooXBar"})

    percent = (await client.get(URL, params={"search": "50%"})).json()
    under = (await client.get(URL, params={"search": "o_B"})).json()

    assert _ids(percent) == [literal_percent["id"]]
    assert _ids(under) == [underscore["id"]]


async def test_blank_search_filters_nothing(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    await _create(client, project)
    await _create(client, project)

    blank = (await client.get(URL, params={"search": "   "})).json()
    empty = (await client.get(URL, params={"search": ""})).json()

    assert blank["total"] == empty["total"] == 2


async def test_search_trims_the_text(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    kept = await _create(client, project, bill_to={"name": "Globex"})
    await _create(client, project, bill_to={"name": "Initech"})

    body = (await client.get(URL, params={"search": "  globex "})).json()

    assert _ids(body) == [kept["id"]]


async def test_search_combines_with_the_filters(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session, name="Alpha")
    other = await make_project(db_session, name="Beta")
    kept = await _create(client, project, bill_to={"name": "Globex"})
    await _create(client, other, bill_to={"name": "Globex"})
    await _create(client, project, bill_to={"name": "Initech"})
    void = await make_issued_invoice(
        db_session, "2026-0001", status="void", project=project
    )
    void.bill_to_name = "Globex"
    await db_session.commit()

    scoped = (
        await client.get(
            URL, params={"search": "globex", "project_id": str(project.id)}
        )
    ).json()
    with_void = (
        await client.get(
            URL,
            params={
                "search": "globex",
                "project_id": str(project.id),
                "status": ["draft", "void"],
            },
        )
    ).json()

    # Void is hidden by default, and the other project's match is filtered out.
    assert _ids(scoped) == [kept["id"]]
    assert scoped["total"] == 1
    assert with_void["total"] == 2


async def test_search_counts_each_invoice_once_and_paginates_the_matches(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    db_session.add_all(
        Invoice(
            project_id=project.id,
            currency_code="EUR",
            bill_from_name="F",
            bill_to_name=f"Match {n}" if n < 51 else f"Other {n}",
            subtotal=Decimal(0),
            total=Decimal(0),
        )
        for n in range(54)
    )
    await db_session.commit()
    line = {"quantity": "1", "uom": "ea", "unit_price": "10"}
    twice = await _create(
        client,
        project,
        bill_to={"name": "Twice"},
        lines=[
            {"description": "Zeta one", **line},
            {"description": "Zeta two", **line},
        ],
    )

    matches = (await client.get(URL, params={"search": "match", "page": 2})).json()
    both_lines = (await client.get(URL, params={"search": "zeta"})).json()

    assert matches["total"] == 51
    assert len(matches["items"]) == 1
    assert _ids(both_lines) == [twice["id"]]
    assert both_lines["total"] == 1
