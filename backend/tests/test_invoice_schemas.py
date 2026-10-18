import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.invoice import (
    GenerateTimeRequest,
    InvoiceLineWrite,
    InvoicePayeeWrite,
    InvoiceWrite,
    PartyWrite,
)

ADDRESS = {"line1": "12 Rue de la Paix", "city": "Paris", "country_code": "fr"}
PAYEE = {
    "payment_means_code": "58",
    "account_scheme": "iban",
    "account_identifier": "be71 0961 2345 6769",
    "currency_code": "eur",
}


def _invoice(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": str(uuid.uuid4()),
        "bill_from": {"name": "Ifrit Consulting"},
        "bill_to": {"name": "ACME"},
    }
    body.update(overrides)
    return body


def _line(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "description": "Senior developer",
        "quantity": "1",
        "uom": "hours",
        "unit_price": "95",
    }
    body.update(overrides)
    return body


# --- parties ---------------------------------------------------------------------


def test_party_name_is_trimmed_and_required() -> None:
    assert PartyWrite(name="  ACME ").name == "ACME"
    with pytest.raises(ValidationError):
        PartyWrite(name="   ")
    with pytest.raises(ValidationError):
        PartyWrite(name="x" * 256)


def test_party_address_is_all_or_nothing() -> None:
    party = PartyWrite.model_validate({"name": "ACME", "address": ADDRESS})
    assert party.address is not None
    assert party.address.country_code == "FR"
    assert PartyWrite(name="ACME").address is None
    with pytest.raises(ValidationError):
        PartyWrite.model_validate({"name": "ACME", "address": {"city": "Paris"}})


# --- lines -----------------------------------------------------------------------


def test_zero_quantity_is_allowed_and_negative_is_not() -> None:
    assert InvoiceLineWrite.model_validate(_line(quantity="0")).quantity == 0
    with pytest.raises(ValidationError):
        InvoiceLineWrite.model_validate(_line(quantity="-1"))


def test_quantity_has_at_most_five_decimals() -> None:
    line = InvoiceLineWrite.model_validate(_line(quantity="1.42857"))
    assert line.quantity == Decimal("1.42857")
    # Trailing zeros are not decimals that matter.
    InvoiceLineWrite.model_validate(_line(quantity="2.5000000"))
    with pytest.raises(ValidationError):
        InvoiceLineWrite.model_validate(_line(quantity="1.428571"))


def test_unit_price_may_be_negative_with_four_decimals() -> None:
    assert InvoiceLineWrite.model_validate(_line(unit_price="-250")).unit_price == -250
    InvoiceLineWrite.model_validate(_line(unit_price="12.3456"))
    with pytest.raises(ValidationError):
        InvoiceLineWrite.model_validate(_line(unit_price="12.34567"))


def test_description_is_trimmed_required_and_capped() -> None:
    assert (
        InvoiceLineWrite.model_validate(_line(description=" Fee ")).description == "Fee"
    )
    with pytest.raises(ValidationError):
        InvoiceLineWrite.model_validate(_line(description="  "))
    with pytest.raises(ValidationError):
        InvoiceLineWrite.model_validate(_line(description="x" * 501))


def test_at_most_200_lines() -> None:
    InvoiceWrite.model_validate(_invoice(lines=[_line()] * 200))
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(_invoice(lines=[_line()] * 201))


# --- references ------------------------------------------------------------------


def test_at_most_50_references() -> None:
    reference = {"kind": "purchase_order", "value": "PO-1"}
    InvoiceWrite.model_validate(_invoice(references=[reference] * 50))
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(_invoice(references=[reference] * 51))


def test_custom_reference_label_rule() -> None:
    InvoiceWrite.model_validate(
        _invoice(references=[{"kind": "custom", "label": "Framework", "value": "FW-1"}])
    )
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(
            _invoice(references=[{"kind": "custom", "value": "X"}])
        )
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(
            _invoice(references=[{"kind": "contract", "label": "L", "value": "X"}])
        )


# --- payment terms and period ----------------------------------------------------


def test_preset_and_fixed_date_are_exclusive() -> None:
    InvoiceWrite.model_validate(_invoice(payment_terms="net_30"))
    InvoiceWrite.model_validate(_invoice(due_date="2026-12-01"))
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(
            _invoice(payment_terms="net_30", due_date="2026-12-01")
        )


def test_unknown_preset_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(_invoice(payment_terms="net_45"))


def test_period_rules() -> None:
    InvoiceWrite.model_validate(
        _invoice(period_start="2026-01-01", period_end="2026-12-31")
    )
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(_invoice(period_start="2026-01-01"))
    with pytest.raises(ValidationError):
        InvoiceWrite.model_validate(
            _invoice(period_start="2026-02-01", period_end="2026-01-31")
        )


def test_generate_period_is_at_most_366_days() -> None:
    ids = [uuid.uuid4()]
    project = uuid.uuid4()
    GenerateTimeRequest(
        kind="time",
        project_id=project,
        service_line_ids=ids,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),  # a leap year: 366 days
    )
    with pytest.raises(ValidationError):
        GenerateTimeRequest(
            kind="time",
            project_id=project,
            service_line_ids=ids,
            period_start=date(2025, 1, 1),
            period_end=date(2026, 1, 2),
        )
    with pytest.raises(ValidationError):
        GenerateTimeRequest(
            kind="time",
            project_id=project,
            service_line_ids=ids,
            period_start=date(2026, 2, 1),
            period_end=date(2026, 1, 31),
        )


# --- payee details ---------------------------------------------------------------


def test_payee_is_normalized_like_a_company_account() -> None:
    payee = InvoicePayeeWrite.model_validate(
        {**PAYEE, "bic": "gebabebb", "bank_name": " "}
    )
    assert payee.account_identifier == "BE71096123456769"
    assert payee.currency_code == "EUR"
    assert payee.bic == "GEBABEBB"
    assert payee.bank_name is None


def test_payee_iban_checksum() -> None:
    with pytest.raises(ValidationError):
        InvoicePayeeWrite.model_validate(
            {**PAYEE, "account_identifier": "BE71096123456768"}
        )


def test_sepa_requires_iban() -> None:
    with pytest.raises(ValidationError):
        InvoicePayeeWrite.model_validate(
            {**PAYEE, "account_scheme": "other", "account_identifier": "123-456"}
        )


def test_payee_bic_shape() -> None:
    with pytest.raises(ValidationError):
        InvoicePayeeWrite.model_validate({**PAYEE, "bic": "GEBABEBB0"})


def test_payee_bank_address_is_all_or_nothing() -> None:
    InvoicePayeeWrite.model_validate({**PAYEE, "bank_address": ADDRESS})
    with pytest.raises(ValidationError):
        InvoicePayeeWrite.model_validate(
            {**PAYEE, "bank_address": {"city": "Brussels"}}
        )


def test_payee_currency_is_any_iso_code() -> None:
    # Not checked against the enabled currencies: a copy outlives a disabled currency.
    InvoicePayeeWrite.model_validate({**PAYEE, "currency_code": "XAU"})
    with pytest.raises(ValidationError):
        InvoicePayeeWrite.model_validate({**PAYEE, "currency_code": "EURO"})


def test_payee_has_no_primary_flag() -> None:
    assert "is_primary" not in InvoicePayeeWrite.model_fields


def test_payee_may_be_absent() -> None:
    assert InvoiceWrite.model_validate(_invoice()).payee is None
    assert InvoiceWrite.model_validate(_invoice(payee=PAYEE)).payee is not None
