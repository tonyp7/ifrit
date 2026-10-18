import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from app.models.invoice import Invoice, InvoiceTax, TaxBaseMode
from app.services.invoice_service import ComputedTax, TaxInput, compute_taxes
from tests.invoice_helpers import login, make_project

URL = "/api/invoices"
SUBTOTAL = Decimal("19037.50")
# Lines that add up to 19,037.50, the subtotal of the worked example.
LINES = [
    {
        "description": "Senior developer",
        "quantity": "152.5",
        "uom": "hours",
        "unit_price": "95",
    },
    {"description": "Architect", "quantity": "40", "uom": "hours", "unit_price": "120"},
    {"description": "Discount", "quantity": "1", "uom": "ea", "unit_price": "-250"},
]


def _rate(rate: str, mode: TaxBaseMode = "subtotal") -> TaxInput:
    return TaxInput(
        base_mode=mode,
        rate=Decimal(rate),
        amount=None,
        amount_set_by_hand=False,
    )


def _by_hand(amount: str, mode: TaxBaseMode = "subtotal") -> TaxInput:
    return TaxInput(
        base_mode=mode,
        rate=None,
        amount=Decimal(amount),
        amount_set_by_hand=True,
    )


EXAMPLE = [_rate("5"), _rate("9.975", "cumulative"), _by_hand("100.00")]


# --- the calculation -------------------------------------------------------------


def test_the_worked_example() -> None:
    gst, qst, eco = compute_taxes(SUBTOTAL, EXAMPLE, 2)

    assert (gst.base_amount, gst.amount) == (SUBTOTAL, Decimal("951.88"))
    assert (qst.base_amount, qst.amount) == (Decimal("19989.38"), Decimal("1993.94"))
    assert (eco.base_amount, eco.amount, eco.rate) == (
        SUBTOTAL,
        Decimal("100.00"),
        Decimal("0.525"),
    )
    assert SUBTOTAL + gst.amount + qst.amount + eco.amount == Decimal("22083.32")


def test_the_first_row_is_always_on_the_subtotal() -> None:
    (first,) = compute_taxes(SUBTOTAL, [_rate("5", "cumulative")], 2)

    assert first.base_mode == "subtotal"
    assert first.base_amount == SUBTOTAL


def test_a_hand_set_amount_on_a_zero_base_has_no_rate() -> None:
    assert compute_taxes(Decimal(0), [_by_hand("10.00")], 2) == [
        ComputedTax(
            base_mode="subtotal",
            rate=None,
            amount=Decimal("10.00"),
            base_amount=Decimal(0),
        )
    ]


def test_a_rate_too_large_to_store_counts_as_unknown() -> None:
    (row,) = compute_taxes(Decimal("0.01"), [_by_hand("99999999.00")], 2)

    assert row.rate is None


def test_a_negative_subtotal_gives_negative_amounts() -> None:
    (row,) = compute_taxes(Decimal("-500.00"), [_rate("10")], 2)

    assert row.amount == Decimal("-50.00")


def test_order_changes_the_compounding_result() -> None:
    reordered = compute_taxes(SUBTOTAL, [_rate("9.975"), _rate("5", "cumulative")], 2)

    assert reordered[0].amount == Decimal("1898.99")
    assert reordered[1].base_amount == Decimal("20936.49")
    assert reordered[1].amount == Decimal("1046.82")


def test_amounts_round_to_the_currency() -> None:
    (row,) = compute_taxes(Decimal(333), [_rate("10")], 0)

    assert row.amount == Decimal(33)


# --- through the API -------------------------------------------------------------


def _tax(label: str, mode: str = "subtotal", **values: Any) -> dict[str, Any]:
    return {"label": label, "base_mode": mode, **values}


EXAMPLE_TAXES = [
    _tax("GST", rate="5"),
    _tax("QST", "cumulative", rate="9.975"),
    _tax("Eco levy", amount="100.00", amount_set_by_hand=True),
]


def _body(project, **overrides: Any) -> dict[str, Any]:
    return {
        "project_id": str(project.id),
        "bill_from": {"name": "Ifrit"},
        "bill_to": {"name": "ACME"},
        "lines": LINES,
        "taxes": EXAMPLE_TAXES,
        **overrides,
    }


async def _save(client, project, **overrides: Any):
    return await client.post(URL, json=_body(project, **overrides))


async def test_saving_stores_the_computed_rows_and_total(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    response = await _save(client, project)

    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(body["subtotal"]) == SUBTOTAL
    assert Decimal(body["total"]) == Decimal("22083.32")
    assert [
        (t["label"], t["base_mode"], t["amount_set_by_hand"]) for t in body["taxes"]
    ] == [
        ("GST", "subtotal", False),
        ("QST", "cumulative", False),
        ("Eco levy", "subtotal", True),
    ]
    assert [Decimal(t["amount"]) for t in body["taxes"]] == [
        Decimal("951.88"),
        Decimal("1993.94"),
        Decimal("100.00"),
    ]
    assert [Decimal(t["base_amount"]) for t in body["taxes"]] == [
        SUBTOTAL,
        Decimal("19989.38"),
        SUBTOTAL,
    ]
    assert Decimal(body["taxes"][2]["rate"]) == Decimal("0.525")

    # What is stored equals a fresh computation from the stored rows.
    db_session.expire_all()
    invoice = await db_session.get(Invoice, uuid.UUID(body["id"]))
    assert invoice is not None
    rows = (
        (
            await db_session.execute(
                select(InvoiceTax)
                .where(InvoiceTax.invoice_id == invoice.id)
                .order_by(InvoiceTax.position)
            )
        )
        .scalars()
        .all()
    )
    fresh = compute_taxes(
        invoice.subtotal,
        [TaxInput(r.base_mode, r.rate, r.amount, r.amount_set_by_hand) for r in rows],
        2,
    )
    assert [(r.amount, r.base_amount, r.rate) for r in rows] == [
        (f.amount, f.base_amount, f.rate) for f in fresh
    ]
    assert invoice.total == invoice.subtotal + sum(r.amount for r in rows)


async def test_the_value_not_typed_is_ignored(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    body = (
        await _save(
            client,
            project,
            taxes=[
                _tax("GST", rate="5", amount="1"),
                _tax("Levy", rate="50", amount="100", amount_set_by_hand=True),
            ],
        )
    ).json()

    assert Decimal(body["taxes"][0]["amount"]) == Decimal("951.88")
    assert Decimal(body["taxes"][1]["rate"]) == Decimal("0.525")


async def test_the_first_row_is_stored_on_the_subtotal(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    body = (
        await _save(client, project, taxes=[_tax("QST", "cumulative", rate="5")])
    ).json()

    assert body["taxes"][0]["base_mode"] == "subtotal"


async def test_no_tax_rows_total_equals_subtotal(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    body = (await _save(client, project, taxes=[])).json()

    assert body["taxes"] == []
    assert Decimal(body["total"]) == Decimal(body["subtotal"])


@pytest.mark.parametrize(
    "taxes",
    [
        [_tax("VAT", rate="100.5")],
        [_tax("VAT", rate="-1")],
        [_tax("VAT", rate="9.9755")],
        [_tax("VAT")],
        [_tax("Levy", amount_set_by_hand=True)],
        [_tax("   ", rate="5")],
        [_tax("x" * 101, rate="5")],
        [_tax("VAT", "compound", rate="5")],
        [_tax(f"T{n}", rate="1") for n in range(21)],
    ],
)
async def test_invalid_tax_rows_are_422(client, db_session, taxes) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    assert (await _save(client, project, taxes=taxes)).status_code == 422


async def test_a_jpy_hand_set_amount_with_decimals_is_422(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session, currency="JPY")
    levy = [_tax("Levy", amount="10.5", amount_set_by_hand=True)]

    assert (await _save(client, project, taxes=levy)).status_code == 422
    whole = [_tax("Levy", amount="10", amount_set_by_hand=True)]
    assert (await _save(client, project, taxes=whole)).status_code == 201


async def test_a_rate_with_three_decimals_and_twenty_rows_save(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)

    body = (
        await _save(
            client, project, taxes=[_tax(f"T{n}", rate="9.975") for n in range(20)]
        )
    ).json()

    assert len(body["taxes"]) == 20
    assert Decimal(body["taxes"][0]["rate"]) == Decimal("9.975")


async def test_a_save_replaces_the_rows_in_the_order_sent(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = (await _save(client, project)).json()

    reordered = [EXAMPLE_TAXES[1], EXAMPLE_TAXES[0]]
    patched = (
        await client.patch(
            f"{URL}/{created['id']}", json=_body(project, taxes=reordered)
        )
    ).json()

    assert [t["label"] for t in patched["taxes"]] == ["QST", "GST"]
    # QST moved first, so it is now on the subtotal, and GST compounds on nothing.
    assert patched["taxes"][0]["base_mode"] == "subtotal"
    assert Decimal(patched["taxes"][0]["amount"]) == Decimal("1898.99")
    assert Decimal(patched["taxes"][1]["base_amount"]) == SUBTOTAL


async def test_duplicate_keeps_rows_order_and_flags(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    source = (await _save(client, project)).json()

    copy = (await client.post(f"{URL}/{source['id']}/duplicate")).json()

    def shape(body: dict[str, Any]) -> list[tuple[Any, ...]]:
        return [
            (
                t["label"],
                t["base_mode"],
                t["rate"],
                t["amount"],
                t["amount_set_by_hand"],
            )
            for t in body["taxes"]
        ]

    assert shape(copy) == shape(source)
    assert copy["total"] == source["total"]


async def test_issuing_freezes_the_rows(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    created = (await _save(client, project, taxes=[_tax("GST", rate="5")])).json()

    issued = await client.post(f"{URL}/{created['id']}/issue")
    patch = await client.patch(f"{URL}/{created['id']}", json=_body(project, taxes=[]))

    assert issued.status_code == 200, issued.text
    (row,) = issued.json()["taxes"]
    assert (
        Decimal(row["rate"]),
        Decimal(row["base_amount"]),
        Decimal(row["amount"]),
    ) == (
        Decimal(5),
        SUBTOTAL,
        Decimal("951.88"),
    )
    assert Decimal(issued.json()["total"]) == SUBTOTAL + Decimal("951.88")
    assert patch.status_code == 409


def _codes(body: dict[str, Any]) -> set[str]:
    return {warning["code"] for warning in body["warnings"]}


async def test_tax_warnings_on_the_draft_and_the_preview(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    zero = [{"description": "Free", "quantity": "1", "uom": "ea", "unit_price": "0"}]
    negative = [
        {"description": "Credit", "quantity": "1", "uom": "ea", "unit_price": "-500"}
    ]

    zero_base = (
        await _save(
            client,
            project,
            lines=zero,
            taxes=[_tax("Levy", amount="10.00", amount_set_by_hand=True)],
        )
    ).json()
    below_zero = (
        await _save(client, project, lines=negative, taxes=[_tax("GST", rate="10")])
    ).json()
    plain = (await _save(client, project)).json()
    preview = (await client.get(f"{URL}/{below_zero['id']}/issue-preview")).json()

    assert zero_base["taxes"][0]["rate"] is None
    assert "tax_rate_not_derivable" in _codes(zero_base)
    assert Decimal(below_zero["taxes"][0]["amount"]) == Decimal("-50.00")
    assert "negative_subtotal" in _codes(below_zero)
    assert {"tax_rate_not_derivable", "negative_subtotal"}.isdisjoint(_codes(plain))
    assert "negative_subtotal" in _codes(preview)
    assert preview["blocking"] == []
