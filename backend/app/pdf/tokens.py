"""The placeholders a template can use: the one catalogue the engine that fills them and the check
that validates an upload share. What each one prints, with an example, is in the user guide (the
invoice template guide), which a test keeps in step with this list."""

from dataclasses import dataclass
from typing import Literal

# `value` is replaced by text; `block` expands to one paragraph per item and must be alone in
# its paragraph; `lines` is the line-items table and must be alone in its paragraph.
TokenKind = Literal["value", "block", "lines"]


@dataclass(frozen=True)
class Token:
    name: str
    kind: TokenKind


# Party and bank placeholders exist once per party, with these endings.
_ADDRESS = (
    "line1",
    "line2",
    "line3",
    "city",
    "postal_zone",
    "country_subdivision",
    "country_code",
    "country",
    "address",
)

REFERENCE_KINDS = (
    "purchase_order",
    "sales_order",
    "contract",
    "buyer_reference",
    "accounting_reference",
    "project_reference",
    "document_reference",
)


def _values(*names: str) -> list[Token]:
    return [Token(name, "value") for name in names]


def _blocks(*names: str) -> list[Token]:
    return [Token(name, "block") for name in names]


def _party(prefix: str) -> list[Token]:
    return [
        *_values(f"{prefix}_name", *(f"{prefix}_{part}" for part in _ADDRESS)),
        *_blocks(f"{prefix}_address_lines"),
        *_values(
            f"{prefix}_vat_id", f"{prefix}_registration_id", f"{prefix}_peppol_id"
        ),
        *_blocks(f"{prefix}_identifiers"),
    ]


_DOCUMENT = _values(
    "document_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "payment_terms",
    "payment_terms_code",
    "period_start",
    "period_end",
    "period",
    "status",
    "issued_at",
    "generated_at",
    "currency_code",
    "line_count",
    "draft_watermark",
)

_PAYMENT = [
    *_values(
        "payment_means",
        "payment_means_code",
        "payee_account_name",
        "payee_account_scheme",
        "payee_account_identifier",
        "payee_account_identifier_raw",
        "payee_currency_code",
        "payee_bic",
        "payee_bank_name",
        *(f"payee_bank_{part}" for part in _ADDRESS),
    ),
    *_blocks("payee_bank_address_lines"),
]

_AMOUNTS = _values(
    "subtotal",
    "tax_total",
    "total",
    "subtotal_with_currency",
    "tax_total_with_currency",
    "total_with_currency",
)

_REFERENCES = [
    *_blocks("references"),
    *_values(*(f"reference_{kind}" for kind in REFERENCE_KINDS), "reference_custom"),
]

CATALOGUE: tuple[Token, ...] = (
    *_DOCUMENT,
    *_party("bill_from"),
    *_party("bill_to"),
    *_PAYMENT,
    *_AMOUNTS,
    *_REFERENCES,
    Token("invoice_lines", "lines"),
)

TOKENS: dict[str, Token] = {token.name: token for token in CATALOGUE}
