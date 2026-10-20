"""The values a template's placeholders stand for, worked out from an invoice.

It takes an `Invoice` (a saved one, or a transient one built from a form) and does no database
access, so a draft preview and an issued invoice produce their values the same way."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models.invoice import Invoice
from app.pdf import format as fmt
from app.pdf.countries import COUNTRY_NAMES
from app.pdf.lines import LineRow, LinesData, TaxRow
from app.pdf.odt import TemplateData
from app.pdf.tokens import REFERENCE_KINDS

NOT_ASSIGNED = "Assigned when issued"
NOT_CALCULATED = "Calculated when issued"

_PAYMENT_TERMS = {
    "due_on_receipt": "Due on receipt",
    "net_7": "NET 7",
    "net_15": "NET 15",
    "net_30": "NET 30",
    "net_60": "NET 60",
    "net_90": "NET 90",
    "eom": "End of month",
    "eom_15": "End of month + 15",
    "eom_30": "End of month + 30",
    "eom_60": "End of month + 60",
    "eom_90": "End of month + 90",
}
_PAYMENT_MEANS = {
    "30": "Credit transfer",
    "42": "Bank transfer",
    "58": "SEPA credit transfer",
}
_UNITS = {"hours": "Hour(s)", "days": "Day(s)", "ea": "Each"}
_REFERENCE_NAMES = {
    "purchase_order": "Purchase order",
    "sales_order": "Sales order",
    "contract": "Contract",
    "buyer_reference": "Buyer reference",
    "accounting_reference": "Accounting reference",
    "project_reference": "Project reference",
    "document_reference": "Document reference",
}
_IDENTIFIER_NAMES = {
    "vat": ("VAT", "vat_id"),
    "legal_registration": ("Registration", "registration_id"),
    "peppol_participant": ("Peppol", "peppol_id"),
}
_PARTY_FIELDS = (
    "line1",
    "line2",
    "line3",
    "city",
    "postal_zone",
    "country_subdivision",
)


def _country(code: str | None) -> str:
    return COUNTRY_NAMES.get(code, code) if code else ""


def _address_lines(prefix: str, invoice: Invoice) -> list[str]:
    """One text per printed line: lines 1 to 3, `postal city`, state, country."""
    if not getattr(invoice, f"{prefix}_country_code"):
        return []

    def get(name: str) -> str:
        return getattr(invoice, f"{prefix}_{name}") or ""

    town = " ".join(part for part in (get("postal_zone"), get("city")) if part)
    lines = [get("line1"), get("line2"), get("line3"), town, get("country_subdivision")]
    lines.append(_country(get("country_code")))
    return [line for line in lines if line]


def _address_values(prefix: str, out_prefix: str, invoice: Invoice) -> dict[str, str]:
    values = {
        f"{out_prefix}_{name}": getattr(invoice, f"{prefix}_{name}") or ""
        for name in (*_PARTY_FIELDS, "country_code")
    }
    values[f"{out_prefix}_country"] = _country(
        getattr(invoice, f"{prefix}_country_code")
    )
    values[f"{out_prefix}_address"] = ", ".join(_address_lines(prefix, invoice))
    return values


def _identifier_values(
    prefix: str, identifiers: Sequence[dict[str, Any]]
) -> tuple[dict[str, str], list[str]]:
    values = {
        f"{prefix}_vat_id": "",
        f"{prefix}_registration_id": "",
        f"{prefix}_peppol_id": "",
    }
    block: list[str] = []
    for identifier in identifiers:
        known = _IDENTIFIER_NAMES.get(identifier["id_type"])
        if known is None:
            continue
        label, suffix = known
        block.append(f"{label}: {identifier['id_value']}")
        # The list is primary first, so the first of a type is the primary one.
        if not values[f"{prefix}_{suffix}"]:
            values[f"{prefix}_{suffix}"] = identifier["id_value"]
    return values, block


def _references(invoice: Invoice) -> tuple[dict[str, str], list[str]]:
    block: list[str] = []
    by_kind: dict[str, list[str]] = {kind: [] for kind in REFERENCE_KINDS}
    custom: list[str] = []
    for reference in invoice.references:
        if reference.kind == "custom":
            text = f"{reference.label}: {reference.value}"
            custom.append(text)
            block.append(text)
        else:
            by_kind[reference.kind].append(reference.value)
            block.append(f"{_REFERENCE_NAMES[reference.kind]}: {reference.value}")
    values = {f"reference_{kind}": ", ".join(items) for kind, items in by_kind.items()}
    values["reference_custom"] = "; ".join(custom)
    return values, block


def build_template_data(
    invoice: Invoice,
    *,
    minor_unit: int,
    document_name: str,
    vendor_identifiers: Sequence[dict[str, Any]],
    client_identifiers: Sequence[dict[str, Any]],
    now: datetime,
) -> TemplateData:
    """Everything the template can ask for. `invoice.status` decides what is assigned: a
    draft has no number, no date and possibly no due date yet, and carries the DRAFT mark."""
    draft = invoice.status == "draft"
    values: dict[str, str] = {}
    blocks: dict[str, list[str]] = {}

    values["document_name"] = document_name
    values["invoice_number"] = NOT_ASSIGNED if draft else invoice.number or ""
    if draft:
        values["invoice_date"] = NOT_ASSIGNED
    else:
        values["invoice_date"] = (
            fmt.date_text(invoice.invoice_date) if invoice.invoice_date else ""
        )
    if draft and invoice.payment_terms:
        values["due_date"] = NOT_CALCULATED
    else:
        values["due_date"] = fmt.date_text(invoice.due_date) if invoice.due_date else ""
    values["payment_terms"] = _PAYMENT_TERMS.get(invoice.payment_terms or "", "")
    values["payment_terms_code"] = invoice.payment_terms or ""
    start: date | None = invoice.period_start
    end: date | None = invoice.period_end
    values["period_start"] = fmt.date_text(start) if start else ""
    values["period_end"] = fmt.date_text(end) if end else ""
    values["period"] = fmt.period_text(start, end) if start and end else ""
    values["status"] = "Draft" if draft else "Issued"
    values["issued_at"] = (
        fmt.datetime_text(invoice.issued_at) if invoice.issued_at and not draft else ""
    )
    values["generated_at"] = fmt.datetime_text(now)
    values["currency_code"] = invoice.currency_code
    values["line_count"] = str(len(invoice.lines))
    values["draft_watermark"] = "DRAFT" if draft else ""

    for prefix, who, identifiers in (
        ("bill_from", "bill_from", vendor_identifiers),
        ("bill_to", "bill_to", client_identifiers),
    ):
        values[f"{prefix}_name"] = getattr(invoice, f"{who}_name")
        values.update(_address_values(who, prefix, invoice))
        blocks[f"{prefix}_address_lines"] = _address_lines(who, invoice)
        identifier_values, block = _identifier_values(prefix, identifiers)
        values.update(identifier_values)
        blocks[f"{prefix}_identifiers"] = block

    has_payee = bool(invoice.payee_account_identifier)
    values["payment_means"] = _PAYMENT_MEANS.get(
        invoice.payee_payment_means_code or "", ""
    )
    values["payment_means_code"] = invoice.payee_payment_means_code or ""
    values["payee_account_name"] = invoice.payee_account_name or ""
    scheme = invoice.payee_account_scheme
    values["payee_account_scheme"] = {"iban": "IBAN", "other": "Other"}.get(
        scheme or "", ""
    )
    identifier = invoice.payee_account_identifier or ""
    values["payee_account_identifier"] = (
        fmt.iban_groups(identifier) if has_payee and scheme == "iban" else identifier
    )
    values["payee_account_identifier_raw"] = identifier
    values["payee_currency_code"] = invoice.payee_currency_code or ""
    values["payee_bic"] = invoice.payee_bic or ""
    values["payee_bank_name"] = invoice.payee_bank_name or ""
    values.update(_address_values("payee_bank", "payee_bank", invoice))
    blocks["payee_bank_address_lines"] = _address_lines("payee_bank", invoice)

    taxes_total = sum((tax.amount for tax in invoice.taxes), Decimal(0))
    amounts = {
        "subtotal": invoice.subtotal,
        "tax_total": taxes_total,
        "total": invoice.total,
    }
    for name, amount in amounts.items():
        values[name] = fmt.money(amount, minor_unit)
        values[f"{name}_with_currency"] = f"{invoice.currency_code} {values[name]}"

    reference_values, blocks["references"] = _references(invoice)
    values.update(reference_values)

    lines = LinesData(
        currency=invoice.currency_code,
        rows=[
            LineRow(
                description=line.description,
                quantity=fmt.quantity(line.quantity),
                unit=_UNITS[line.uom],
                unit_price=fmt.unit_price(line.unit_price, minor_unit),
                amount=fmt.money(line.amount, minor_unit),
            )
            for line in invoice.lines
        ],
        subtotal=values["subtotal"],
        taxes=[
            TaxRow(
                label=tax.label
                if tax.amount_set_by_hand or tax.rate is None
                else f"{tax.label} ({fmt.rate(tax.rate)} %)",
                amount=fmt.money(tax.amount, minor_unit),
            )
            for tax in invoice.taxes
        ],
        total=values["total"],
    )
    return TemplateData(values=values, blocks=blocks, lines=lines)
