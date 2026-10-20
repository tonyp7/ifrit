"""The placeholders a template can use: one catalogue shared by the engine that fills them,
the builder that supplies their values and the help shown to template authors."""

from dataclasses import dataclass
from typing import Literal

# `value` is replaced by text; `block` expands to one paragraph per item and must be alone in
# its paragraph; `lines` is the line-items table and must be alone in its paragraph.
TokenKind = Literal["value", "block", "lines"]


@dataclass(frozen=True)
class Token:
    name: str
    kind: TokenKind
    description: str
    example: str


def _party(prefix: str, who: str) -> list[Token]:
    return [
        Token(f"{prefix}_name", "value", f"The {who}'s name", "Acme Pte Ltd"),
        Token(
            f"{prefix}_line1",
            "value",
            f"First address line of the {who}",
            "8 Ah Soo Garden",
        ),
        Token(
            f"{prefix}_line2", "value", f"Second address line of the {who}", "Unit 4"
        ),
        Token(f"{prefix}_line3", "value", f"Third address line of the {who}", ""),
        Token(f"{prefix}_city", "value", f"City of the {who}", "Singapore"),
        Token(f"{prefix}_postal_zone", "value", f"Postal code of the {who}", "539960"),
        Token(
            f"{prefix}_country_subdivision",
            "value",
            f"State or province of the {who}",
            "",
        ),
        Token(
            f"{prefix}_country_code", "value", f"ISO country code of the {who}", "SG"
        ),
        Token(
            f"{prefix}_country",
            "value",
            f"Country of the {who}, in English",
            "Singapore",
        ),
        Token(
            f"{prefix}_address",
            "value",
            f"The {who}'s whole address on one line",
            "8 Ah Soo Garden, 539960 Singapore, Singapore",
        ),
        Token(
            f"{prefix}_address_lines",
            "block",
            f"The {who}'s address, one paragraph per line",
            "8 Ah Soo Garden / 539960 Singapore / Singapore",
        ),
        Token(
            f"{prefix}_vat_id",
            "value",
            f"The {who}'s primary VAT identifier",
            "SG123456789",
        ),
        Token(
            f"{prefix}_registration_id",
            "value",
            f"The {who}'s primary legal registration identifier",
            "201912345K",
        ),
        Token(
            f"{prefix}_peppol_id",
            "value",
            f"The {who}'s primary Peppol participant identifier",
            "0195:SGUENT08GA0028A",
        ),
        Token(
            f"{prefix}_identifiers",
            "block",
            f"The {who}'s identifiers, one paragraph each",
            "VAT: SG123456789",
        ),
    ]


_DOCUMENT = [
    Token(
        "document_name",
        "value",
        "The document name setting (Invoice by default)",
        "Invoice",
    ),
    Token("invoice_number", "value", "The invoice number", "INV-2026-0043"),
    Token("invoice_date", "value", "The invoice date", "3 September 2026"),
    Token("due_date", "value", "The due date", "3 October 2026"),
    Token("payment_terms", "value", "The payment terms", "NET 30"),
    Token("payment_terms_code", "value", "The payment terms as a code", "net_30"),
    Token("period_start", "value", "Start of the billed period", "1 August 2026"),
    Token("period_end", "value", "End of the billed period", "31 August 2026"),
    Token("period", "value", "The billed period", "1-31 August 2026"),
    Token("status", "value", "Draft or Issued", "Issued"),
    Token(
        "issued_at", "value", "When the invoice was issued", "3 September 2026 14:05"
    ),
    Token("generated_at", "value", "When this PDF was made", "3 September 2026 14:05"),
    Token("currency_code", "value", "The invoice currency", "USD"),
    Token("line_count", "value", "The number of lines", "3"),
    Token("draft_watermark", "value", "DRAFT on a draft, empty otherwise", "DRAFT"),
]

_PAYMENT = [
    Token("payment_means", "value", "How to pay", "Bank transfer"),
    Token("payment_means_code", "value", "How to pay, as a code", "42"),
    Token("payee_account_name", "value", "The account holder", "Acme Pte Ltd"),
    Token("payee_account_scheme", "value", "IBAN or Other", "IBAN"),
    Token(
        "payee_account_identifier",
        "value",
        "The account number (IBAN in groups of four)",
        "SG12 3456 7890 1234",
    ),
    Token(
        "payee_account_identifier_raw",
        "value",
        "The account number as stored",
        "SG1234567890123456",
    ),
    Token("payee_currency_code", "value", "The account's currency", "USD"),
    Token("payee_bic", "value", "The bank's BIC (SWIFT)", "DBSSSGSG"),
    Token("payee_bank_name", "value", "The bank's name", "DBS Bank"),
    Token(
        "payee_bank_line1",
        "value",
        "First address line of the bank",
        "12 Marina Boulevard",
    ),
    Token("payee_bank_line2", "value", "Second address line of the bank", ""),
    Token("payee_bank_line3", "value", "Third address line of the bank", ""),
    Token("payee_bank_city", "value", "City of the bank", "Singapore"),
    Token("payee_bank_postal_zone", "value", "Postal code of the bank", "018982"),
    Token(
        "payee_bank_country_subdivision", "value", "State or province of the bank", ""
    ),
    Token("payee_bank_country_code", "value", "ISO country code of the bank", "SG"),
    Token(
        "payee_bank_country", "value", "Country of the bank, in English", "Singapore"
    ),
    Token(
        "payee_bank_address",
        "value",
        "The bank's address on one line",
        "12 Marina Boulevard, 018982 Singapore, Singapore",
    ),
    Token(
        "payee_bank_address_lines",
        "block",
        "The bank's address, one paragraph per line",
        "12 Marina Boulevard / 018982 Singapore",
    ),
]

_AMOUNTS = [
    Token("subtotal", "value", "The subtotal", "6,000.00"),
    Token("tax_total", "value", "The sum of the taxes", "420.00"),
    Token("total", "value", "The total", "6,420.00"),
    Token(
        "subtotal_with_currency",
        "value",
        "The subtotal with the currency",
        "USD 6,000.00",
    ),
    Token(
        "tax_total_with_currency", "value", "The taxes with the currency", "USD 420.00"
    ),
    Token(
        "total_with_currency", "value", "The total with the currency", "USD 6,420.00"
    ),
]

REFERENCE_KINDS = (
    "purchase_order",
    "sales_order",
    "contract",
    "buyer_reference",
    "accounting_reference",
    "project_reference",
    "document_reference",
)

_REFERENCES = [
    Token(
        "references",
        "block",
        "The references, one paragraph each",
        "Purchase order: 1070000772",
    ),
    *(
        Token(
            f"reference_{kind}",
            "value",
            f"The values of the {kind.replace('_', ' ')} references",
            "PO-1, PO-2",
        )
        for kind in REFERENCE_KINDS
    ),
    Token(
        "reference_custom",
        "value",
        "The custom references as Label: value",
        "Cost centre: 4410",
    ),
]

_LINES = [
    Token(
        "invoice_lines",
        "lines",
        "The line-items table with subtotal, taxes and total",
        "",
    ),
]

CATALOGUE: tuple[Token, ...] = (
    *_DOCUMENT,
    *_party("bill_from", "vendor"),
    *_party("bill_to", "client"),
    *_PAYMENT,
    *_AMOUNTS,
    *_REFERENCES,
    *_LINES,
)

TOKENS: dict[str, Token] = {token.name: token for token in CATALOGUE}
