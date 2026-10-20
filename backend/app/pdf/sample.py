"""A fixed invoice the template preview and the trial render are filled with, so an author
sees real-looking values without any invoice existing."""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models.invoice import Invoice, InvoiceLine, InvoiceReference, InvoiceTax
from app.pdf.odt import TemplateData
from app.pdf.values import build_template_data

_ISSUED = datetime(2026, 9, 3, 14, 5, tzinfo=UTC)


def sample_template_data() -> TemplateData:
    invoice = Invoice(
        status="issued",
        number="INV-2026-0001",
        invoice_date=date(2026, 9, 3),
        issued_at=_ISSUED,
        due_date=date(2026, 10, 3),
        payment_terms="net_30",
        currency_code="USD",
        currency_minor_unit=2,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        bill_from_name="Sample Consulting Pte. Ltd.",
        bill_from_line1="1 Sample Street",
        bill_from_city="Singapore",
        bill_from_postal_zone="018989",
        bill_from_country_code="SG",
        bill_to_name="Example Client Ltd",
        bill_to_line1="22 Example Road",
        bill_to_line2="Floor 3",
        bill_to_city="Hong Kong",
        bill_to_country_code="HK",
        payee_payment_means_code="42",
        payee_account_scheme="other",
        payee_account_identifier="123-456-789",
        payee_account_name="Sample Consulting Pte. Ltd.",
        payee_currency_code="USD",
        payee_bic="SAMPSGSG",
        payee_bank_name="Sample Bank",
        payee_bank_line1="1 Bank Street",
        payee_bank_city="Singapore",
        payee_bank_postal_zone="018989",
        payee_bank_country_code="SG",
        subtotal=Decimal(6000),
        total=Decimal(6420),
        lines=[
            InvoiceLine(
                position=0,
                description="Consulting services, August 2026",
                quantity=Decimal(20),
                uom="days",
                unit_price=Decimal(300),
                amount=Decimal(6000),
            )
        ],
        references=[
            InvoiceReference(
                position=0, kind="purchase_order", label=None, value="PO-1070000772"
            )
        ],
        taxes=[
            InvoiceTax(
                position=0,
                label="GST",
                base_mode="subtotal",
                rate=Decimal(7),
                amount=Decimal(420),
                amount_set_by_hand=False,
                base_amount=Decimal(6000),
            )
        ],
    )
    data = build_template_data(
        invoice,
        minor_unit=2,
        document_name="Invoice",
        vendor_identifiers=[
            {
                "id_type": "vat",
                "scheme_id": None,
                "id_value": "M2-0000000-0",
                "is_primary": True,
            }
        ],
        client_identifiers=[
            {
                "id_type": "legal_registration",
                "scheme_id": "HKCR",
                "id_value": "12345678",
                "is_primary": True,
            }
        ],
        now=_ISSUED,
    )
    # Shown on the sample so an author sees where the DRAFT mark sits and how it looks.
    data.values["draft_watermark"] = "DRAFT"
    return data
