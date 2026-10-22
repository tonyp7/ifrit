from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.models.invoice import Invoice, InvoiceLine, InvoiceReference, InvoiceTax
from app.models.project import Uom
from app.pdf import format as fmt
from app.pdf.odt import TemplateData
from app.pdf.tokens import TOKENS
from app.pdf.values import (
    NOT_ASSIGNED,
    NOT_CALCULATED,
    ProjectedIssue,
    build_template_data,
)

NOW = datetime(2026, 9, 3, 14, 5, tzinfo=UTC)
VENDOR_IDS = [
    {"id_type": "vat", "scheme_id": None, "id_value": "SG123", "is_primary": True},
    {
        "id_type": "legal_registration",
        "scheme_id": None,
        "id_value": "UEN9",
        "is_primary": True,
    },
    {
        "id_type": "peppol_participant",
        "scheme_id": "0195",
        "id_value": "0195:X",
        "is_primary": True,
    },
    {"id_type": "vat", "scheme_id": None, "id_value": "SG999", "is_primary": False},
    {"id_type": "duns", "scheme_id": None, "id_value": "1", "is_primary": False},
]


def _invoice(**overrides: Any) -> Invoice:
    values: dict[str, Any] = {
        "status": "draft",
        "currency_code": "USD",
        "bill_from_name": "Ifrit Consulting",
        "bill_from_line1": "1 Example Road",
        "bill_from_city": "Singapore",
        "bill_from_postal_zone": "123456",
        "bill_from_country_code": "SG",
        "bill_to_name": "ACME",
        "subtotal": Decimal(6000),
        "total": Decimal(6420),
        "lines": [
            InvoiceLine(
                position=0,
                description="Consulting",
                quantity=Decimal("20.00000"),
                uom="days",
                unit_price=Decimal("300.0000"),
                amount=Decimal(6000),
            )
        ],
        "references": [],
        "taxes": [
            InvoiceTax(
                position=0,
                label="GST",
                base_mode="subtotal",
                rate=Decimal("7.000"),
                amount=Decimal(420),
                amount_set_by_hand=False,
                base_amount=Decimal(6000),
            )
        ],
    }
    values.update(overrides)
    return Invoice(**values)


def _data(
    invoice: Invoice | None = None, minor: int = 2, **kwargs: Any
) -> TemplateData:
    return build_template_data(
        invoice or _invoice(),
        minor_unit=minor,
        document_name=kwargs.pop("document_name", "Invoice"),
        vendor_identifiers=kwargs.pop("vendor_identifiers", []),
        client_identifiers=kwargs.pop("client_identifiers", []),
        now=NOW,
    )


def test_every_catalogue_placeholder_is_supplied() -> None:
    data = _data()
    for name, token in TOKENS.items():
        if token.kind == "value":
            assert name in data.values, name
        elif token.kind == "block":
            assert name in data.blocks, name


def _projected_data(invoice: Invoice, projected: ProjectedIssue) -> TemplateData:
    return build_template_data(
        invoice,
        minor_unit=2,
        document_name="Invoice",
        vendor_identifiers=[],
        client_identifiers=[],
        now=NOW,
        projected=projected,
    )


def test_a_draft_shows_the_values_issuing_it_today_would_give() -> None:
    data = _projected_data(
        _invoice(payment_terms="net_30"),
        ProjectedIssue("INV-2026-0044", date(2026, 10, 14), date(2026, 11, 13)),
    )
    assert data.values["invoice_number"] == "INV-2026-0044"
    assert data.values["invoice_date"] == "14 October 2026"
    assert data.values["due_date"] == "13 November 2026"
    # Still a draft: only the DRAFT mark says so, and nothing says it was issued.
    assert data.values["status"] == "Draft"
    assert data.values["issued_at"] == ""
    assert data.values["draft_watermark"] == "DRAFT"


def test_a_projected_draft_with_no_due_date_prints_none() -> None:
    data = _projected_data(
        _invoice(), ProjectedIssue("INV-2026-0044", date(2026, 10, 14), None)
    )
    assert data.values["due_date"] == ""


def test_projected_values_never_change_an_issued_invoice() -> None:
    invoice = _invoice(
        status="issued", number="INV-1", invoice_date=date(2026, 9, 3), issued_at=NOW
    )
    data = _projected_data(
        invoice, ProjectedIssue("INV-9", date(2026, 10, 14), date(2026, 11, 13))
    )
    assert data.values["invoice_number"] == "INV-1"
    assert data.values["invoice_date"] == "3 September 2026"


def test_a_draft_built_without_projected_values_says_they_come_later() -> None:
    data = _data(_invoice(payment_terms="net_30"))
    assert data.values["invoice_number"] == NOT_ASSIGNED
    assert data.values["invoice_date"] == NOT_ASSIGNED
    assert data.values["due_date"] == NOT_CALCULATED
    assert data.values["status"] == "Draft"
    assert data.values["issued_at"] == ""
    assert data.values["draft_watermark"] == "DRAFT"
    assert data.values["payment_terms"] == "NET 30"
    assert data.values["payment_terms_code"] == "net_30"


def test_a_draft_with_a_fixed_due_date_shows_it() -> None:
    data = _data(_invoice(due_date=date(2026, 9, 30)))
    assert data.values["due_date"] == "30 September 2026"
    assert data.values["payment_terms"] == ""


def test_issued_values_come_from_the_invoice() -> None:
    invoice = _invoice(
        status="issued",
        number="INV-2026-0043",
        invoice_date=date(2026, 9, 3),
        due_date=date(2026, 10, 3),
        payment_terms="net_30",
        issued_at=NOW,
    )
    values = _data(invoice).values
    assert values["invoice_number"] == "INV-2026-0043"
    assert values["invoice_date"] == "3 September 2026"
    assert values["due_date"] == "3 October 2026"
    assert values["status"] == "Issued"
    assert values["draft_watermark"] == ""
    assert values["issued_at"].startswith("3 September 2026 ")
    assert values["generated_at"].startswith("3 September 2026 ")


def test_party_values() -> None:
    invoice = _invoice(
        bill_to_name="Acme Pte Ltd",
        bill_to_line1="1 Example Road",
        bill_to_city="Singapore",
        bill_to_postal_zone="123456",
        bill_to_country_code="SG",
    )
    data = _data(invoice, client_identifiers=[VENDOR_IDS[1]])
    assert data.values["bill_to_name"] == "Acme Pte Ltd"
    assert data.values["bill_to_country"] == "Singapore"
    assert data.values["bill_to_country_code"] == "SG"
    assert (
        data.values["bill_to_address"] == "1 Example Road, 123456 Singapore, Singapore"
    )
    assert data.blocks["bill_to_address_lines"] == [
        "1 Example Road",
        "123456 Singapore",
        "Singapore",
    ]
    assert data.values["bill_to_registration_id"] == "UEN9"
    assert data.blocks["bill_to_identifiers"] == ["Registration: UEN9"]


def test_a_party_without_an_address_has_empty_address_values() -> None:
    data = _data(_invoice(bill_to_name="ACME"))
    assert data.values["bill_to_address"] == ""
    assert data.values["bill_to_country"] == ""
    assert data.blocks["bill_to_address_lines"] == []


def test_identifiers_pick_the_primary_of_each_type_and_skip_other_types() -> None:
    data = _data(vendor_identifiers=VENDOR_IDS)
    assert data.values["bill_from_vat_id"] == "SG123"
    assert data.values["bill_from_peppol_id"] == "0195:X"
    assert data.blocks["bill_from_identifiers"] == [
        "VAT: SG123",
        "Registration: UEN9",
        "Peppol: 0195:X",
        "VAT: SG999",
    ]


def test_state_and_third_address_line_are_included() -> None:
    invoice = _invoice(
        bill_to_line1="1 Main St",
        bill_to_line3="Floor 3",
        bill_to_city="Austin",
        bill_to_postal_zone="78701",
        bill_to_country_subdivision="TX",
        bill_to_country_code="US",
    )
    assert _data(invoice).blocks["bill_to_address_lines"] == [
        "1 Main St",
        "Floor 3",
        "78701 Austin",
        "TX",
        "United States",
    ]


def test_payee_values_and_iban_grouping() -> None:
    invoice = _invoice(
        payee_payment_means_code="58",
        payee_account_scheme="iban",
        payee_account_identifier="SG1234567890123456",
        payee_account_name="Ifrit",
        payee_currency_code="USD",
        payee_bic="EXMPSGSG",
        payee_bank_name="DBS Bank",
        payee_bank_line1="1 Sample Blvd",
        payee_bank_city="Singapore",
        payee_bank_country_code="SG",
    )
    values = _data(invoice).values
    assert values["payment_means"] == "SEPA credit transfer"
    assert values["payment_means_code"] == "58"
    assert values["payee_account_scheme"] == "IBAN"
    assert values["payee_account_identifier"] == "SG12 3456 7890 1234 56"
    assert values["payee_account_identifier_raw"] == "SG1234567890123456"
    assert values["payee_bank_country"] == "Singapore"
    assert values["payee_bank_address"] == "1 Sample Blvd, Singapore, Singapore"


def test_payment_means_are_named_in_words() -> None:
    def means(code: str) -> str:
        scheme = "iban" if code == "58" else "other"
        invoice = _invoice(
            payee_payment_means_code=code,
            payee_account_scheme=scheme,
            payee_account_identifier="SG1234567890123456",
            payee_currency_code="USD",
        )
        return _data(invoice).values["payment_means"]

    assert means("30") == "Wire transfer"
    assert means("42") == "Bank transfer"
    assert means("58") == "SEPA credit transfer"


def test_a_non_iban_account_is_not_regrouped() -> None:
    invoice = _invoice(
        payee_payment_means_code="42",
        payee_account_scheme="other",
        payee_account_identifier="0012 345",
        payee_currency_code="USD",
    )
    values = _data(invoice).values
    assert values["payee_account_identifier"] == "0012 345"
    assert values["payee_account_scheme"] == "Other"
    assert values["payment_means"] == "Bank transfer"


def test_no_payee_account_leaves_payment_values_empty() -> None:
    values = _data().values
    for name in (
        "payment_means",
        "payee_account_identifier",
        "payee_bic",
        "payee_currency_code",
    ):
        assert values[name] == ""


def test_amounts() -> None:
    values = _data().values
    assert values["subtotal"] == "6,000.00"
    assert values["tax_total"] == "420.00"
    assert values["total"] == "6,420.00"
    assert values["total_with_currency"] == "USD 6,420.00"
    assert values["subtotal_with_currency"] == "USD 6,000.00"


def test_amounts_use_the_currency_decimals() -> None:
    invoice = _invoice(
        currency_code="JPY", subtotal=Decimal(6000), total=Decimal(6000), taxes=[]
    )
    assert _data(invoice, minor=0).values["total"] == "6,000"


def test_references_by_kind_and_in_order() -> None:
    invoice = _invoice(
        references=[
            InvoiceReference(
                position=0, kind="purchase_order", label=None, value="PO-1"
            ),
            InvoiceReference(
                position=1, kind="custom", label="Cost centre", value="4410"
            ),
            InvoiceReference(
                position=2, kind="purchase_order", label=None, value="PO-2"
            ),
            InvoiceReference(position=3, kind="custom", label="Site", value="B"),
        ]
    )
    data = _data(invoice)
    assert data.blocks["references"] == [
        "Purchase order: PO-1",
        "Cost centre: 4410",
        "Purchase order: PO-2",
        "Site: B",
    ]
    assert data.values["reference_purchase_order"] == "PO-1, PO-2"
    assert data.values["reference_custom"] == "Cost centre: 4410; Site: B"
    assert data.values["reference_contract"] == ""


def test_period_values() -> None:
    values = _data(
        _invoice(period_start=date(2026, 8, 1), period_end=date(2026, 8, 31))
    ).values
    assert values["period"] == "1-31 August 2026"
    assert values["period_start"] == "1 August 2026"
    assert _data().values["period"] == ""


def test_line_rows_and_tax_labels() -> None:
    data = _data()
    row = data.lines.rows[0]
    assert (row.quantity, row.unit, row.unit_price, row.amount) == (
        "20",
        "Day(s)",
        "300.00",
        "6,000.00",
    )
    assert data.lines.taxes[0].label == "GST (7 %)"
    assert data.lines.currency == "USD" and data.lines.total == "6,420.00"
    assert data.values["line_count"] == "1"


def test_a_hand_set_tax_shows_only_its_name() -> None:
    invoice = _invoice(
        taxes=[
            InvoiceTax(
                position=0,
                label="Levy",
                base_mode="subtotal",
                rate=Decimal("7.000"),
                amount=Decimal(420),
                amount_set_by_hand=True,
                base_amount=Decimal(6000),
            )
        ]
    )
    assert _data(invoice).lines.taxes[0].label == "Levy"


@pytest.mark.parametrize(
    ("uom", "label"), [("hours", "Hour(s)"), ("days", "Day(s)"), ("ea", "Each")]
)
def test_unit_labels(uom: Uom, label: str) -> None:
    invoice = _invoice()
    invoice.lines[0].uom = uom
    assert _data(invoice).lines.rows[0].unit == label


@pytest.mark.parametrize(
    ("preset", "label"),
    [
        ("due_on_receipt", "Due on receipt"),
        ("eom", "End of month"),
        ("eom_90", "End of month + 90"),
    ],
)
def test_payment_terms_labels(preset: str, label: str) -> None:
    assert _data(_invoice(payment_terms=preset)).values["payment_terms"] == label


# --- formatting ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "places", "text"),
    [
        (Decimal(6000), 2, "6,000.00"),
        (Decimal("1234567.891"), 2, "1,234,567.89"),
        (Decimal("-12.5"), 2, "-12.50"),
        (Decimal(6000), 0, "6,000"),
        (Decimal("1.2345"), 3, "1.235"),
        (Decimal(0), 2, "0.00"),
    ],
)
def test_money(value: Decimal, places: int, text: str) -> None:
    assert fmt.money(value, places) == text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("20.00000", "20"),
        ("2.50000", "2.5"),
        ("0.00000", "0"),
        ("1000", "1,000"),
        ("0.12500", "0.125"),
    ],
)
def test_quantity(value: str, text: str) -> None:
    assert fmt.quantity(Decimal(value)) == text


def test_unit_price_is_never_printed_rounded() -> None:
    assert fmt.unit_price(Decimal("300.0000"), 2) == "300.00"
    assert fmt.unit_price(Decimal("12.3456"), 2) == "12.3456"
    assert fmt.unit_price(Decimal("12.5000"), 2) == "12.50"


def test_dates_do_not_depend_on_the_locale() -> None:
    assert fmt.date_text(date(2026, 1, 5)) == "5 January 2026"
    assert (
        fmt.period_text(date(2026, 8, 1), date(2026, 9, 5))
        == "1 August - 5 September 2026"
    )
    assert (
        fmt.period_text(date(2025, 12, 30), date(2026, 1, 2))
        == "30 December 2025 - 2 January 2026"
    )
    assert fmt.period_text(date(2026, 8, 7), date(2026, 8, 7)) == "7 August 2026"
