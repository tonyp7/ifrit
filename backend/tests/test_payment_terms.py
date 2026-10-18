from datetime import date

import pytest

from app.models.invoice import PaymentTerms
from app.services.payment_terms import apply_payment_terms

# The invoicing plan's table, for an invoice issued on 14 Oct 2026; the frontend's
# lib/paymentTerms.test.ts runs the same one.
TABLE: list[tuple[PaymentTerms, date]] = [
    ("due_on_receipt", date(2026, 10, 14)),
    ("net_7", date(2026, 10, 21)),
    ("net_15", date(2026, 10, 29)),
    ("net_30", date(2026, 11, 13)),
    ("net_60", date(2026, 12, 13)),
    ("net_90", date(2027, 1, 12)),
    ("eom", date(2026, 10, 31)),
    ("eom_15", date(2026, 11, 15)),
    ("eom_30", date(2026, 11, 30)),
    ("eom_60", date(2026, 12, 30)),
    ("eom_90", date(2027, 1, 29)),
]


@pytest.mark.parametrize(("preset", "expected"), TABLE)
def test_presets_from_14_october_2026(preset: PaymentTerms, expected: date) -> None:
    assert apply_payment_terms(preset, date(2026, 10, 14)) == expected


def test_end_of_month_in_a_leap_february() -> None:
    assert apply_payment_terms("eom", date(2028, 2, 3)) == date(2028, 2, 29)
