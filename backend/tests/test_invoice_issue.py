import asyncio
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.company import PartyIdentifier, PayeeAccount
from app.models.invoice import Invoice
from app.models.invoice_numbering import InvoiceNumberCounter
from app.models.project import Project
from app.schemas.invoice import InvoiceWrite
from app.services import invoice_service
from app.services.app_settings import update_group
from tests.factories import create_company, create_user
from tests.invoice_helpers import (
    add_service_line,
    ensure_currency,
    log_hours,
    make_consultant,
    make_issued_invoice,
    make_project,
)

OCT_14 = date(2026, 10, 14)
PAYEE: dict[str, Any] = {
    "payment_means_code": "58",
    "account_scheme": "iban",
    "account_identifier": "BE71096123456769",
    "currency_code": "EUR",
    "bic": "GEBABEBB",
}


async def _user(db_session):
    return await create_user(
        db_session, name_id="b@example.com", password="pw", role_name="billing"
    )


async def _draft(
    db_session, project: Project, user_id: uuid.UUID, **overrides: Any
) -> Invoice:
    body: dict[str, Any] = {
        "project_id": project.id,
        "bill_from": {"name": "Ifrit"},
        "bill_to": {"name": "ACME"},
        "lines": [
            {
                "description": "Work",
                "quantity": "10",
                "uom": "hours",
                "unit_price": "95",
            }
        ],
    }
    body.update(overrides)
    invoice = await invoice_service.create_invoice(
        db_session, InvoiceWrite.model_validate(body), user_id
    )
    return invoice


async def _issue(
    db_session, invoice: Invoice, user_id: uuid.UUID, day: date = OCT_14
) -> Invoice:
    issued = await invoice_service.issue(db_session, invoice.id, user_id, day)
    assert issued is not None
    return issued


# --- issuing ---------------------------------------------------------------------


async def test_issue_with_net_30(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id, payment_terms="net_30")

    issued = await _issue(db_session, draft, user.id)

    assert issued.status == "issued"
    assert issued.number == "INV-2026-0001"
    assert issued.invoice_date == OCT_14
    assert issued.due_date == date(2026, 11, 13)
    assert issued.payment_terms == "net_30"
    assert issued.issued_by == user.id
    assert issued.issued_at is not None
    assert issued.currency_minor_unit == 2
    assert issued.document_name == "Invoice"


async def test_numbers_follow_each_other(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    first = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )
    second = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )
    assert [first.number, second.number] == ["INV-2026-0001", "INV-2026-0002"]


async def test_a_fixed_due_date_is_kept_and_none_stays_none(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    fixed = await _issue(
        db_session,
        await _draft(db_session, project, user.id, due_date="2026-12-01"),
        user.id,
    )
    none = await _issue(db_session, await _draft(db_session, project, user.id), user.id)
    assert fixed.due_date == date(2026, 12, 1)
    assert none.due_date is None


async def test_a_draft_with_no_line_cannot_be_issued(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id, lines=[])

    with pytest.raises(invoice_service.NoLinesError):
        await invoice_service.issue(db_session, draft.id, user.id, OCT_14)

    await db_session.refresh(draft)
    assert draft.status == "draft"


async def test_an_issued_invoice_cannot_be_issued_again(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    issued = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )

    with pytest.raises(invoice_service.InvoiceNotDraftError):
        await invoice_service.issue(db_session, issued.id, user.id, OCT_14)


@pytest.mark.parametrize("change", ["closed", "draft", "deleted"])
async def test_the_project_must_be_active(db_session, change: str) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id)
    if change == "deleted":
        project.is_active = False
    elif change == "closed":
        project.status = "closed"
    else:
        project.status = "draft"
    await db_session.commit()

    with pytest.raises(invoice_service.ProjectNotActiveError):
        await invoice_service.issue(db_session, draft.id, user.id, OCT_14)

    project.status, project.is_active = "active", True
    await db_session.commit()
    assert (await _issue(db_session, draft, user.id)).status == "issued"


async def test_a_number_collision_changes_nothing(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    await make_issued_invoice(db_session, "INV-2026-0001", project=project)
    draft = await _draft(db_session, project, user.id)
    draft_id = draft.id

    with pytest.raises(invoice_service.NumberAlreadyUsedError) as caught:
        await invoice_service.issue(db_session, draft_id, user.id, OCT_14)

    assert caught.value.number == "INV-2026-0001"
    assert await db_session.get(InvoiceNumberCounter, ("invoice", "2026")) is None
    reloaded = await db_session.get(Invoice, draft_id)
    assert reloaded is not None
    await db_session.refresh(reloaded)
    assert reloaded.status == "draft"
    assert reloaded.number is None


async def test_concurrent_issues_get_different_numbers(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    drafts = [await _draft(db_session, project, user.id) for _ in range(2)]
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def issue_one(invoice_id: uuid.UUID) -> str | None:
        async with factory() as session:
            issued = await invoice_service.issue(session, invoice_id, user.id, OCT_14)
            return issued.number if issued else None

    numbers = await asyncio.gather(*(issue_one(d.id) for d in drafts))
    assert sorted(n or "" for n in numbers) == ["INV-2026-0001", "INV-2026-0002"]


async def test_issuing_recomputes_the_amounts(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(
        db_session,
        project,
        user.id,
        lines=[
            {
                "description": "Days",
                "quantity": "1.42857",
                "uom": "days",
                "unit_price": "700",
            }
        ],
    )
    for line in draft.lines:
        line.amount = Decimal(0)
    draft.subtotal = draft.total = Decimal(0)
    await db_session.commit()

    issued = await _issue(db_session, draft, user.id)

    assert issued.lines[0].amount == Decimal("1000.00")
    assert issued.total == Decimal("1000.00")


# --- what issuing freezes --------------------------------------------------------


async def test_the_snapshot_does_not_follow_later_changes(db_session) -> None:
    user = await _user(db_session)
    await ensure_currency(db_session, "EUR")
    vendor = await create_company(db_session, legal_name="Ifrit", is_vendor=True)
    vat = PartyIdentifier(
        company_id=vendor.id, id_type="vat", id_value="BE0123456789", is_primary=True
    )
    expired = PartyIdentifier(
        company_id=vendor.id,
        id_type="vat",
        id_value="BE0999",
        valid_to=date(2020, 1, 1),
    )
    internal = PartyIdentifier(company_id=vendor.id, id_type="internal", id_value="X-1")
    account = PayeeAccount(
        company_id=vendor.id,
        payment_means_code="58",
        account_scheme="iban",
        account_identifier="BE71096123456769",
        currency_code="EUR",
        bic="GEBABEBB",
    )
    db_session.add_all([vat, expired, internal, account])
    await db_session.commit()
    project = await make_project(db_session, vendor=vendor)
    issued = await _issue(
        db_session, await _draft(db_session, project, user.id, payee=PAYEE), user.id
    )
    assert issued.vendor_identifiers == [
        {
            "id_type": "vat",
            "scheme_id": None,
            "id_value": "BE0123456789",
            "is_primary": True,
        }
    ]

    vat.id_value = "BE0000000000"
    account.bic = "KREDBEBB"
    admin = await create_user(
        db_session, name_id="a@example.com", password="pw", role_name="administrator"
    )
    await update_group(
        db_session, "invoicing", {"document_name": "Tax Invoice"}, admin.id
    )
    await ensure_currency(db_session, "USD")
    project.invoicing_currency = "USD"
    await db_session.commit()
    await db_session.delete(account)
    await db_session.commit()

    reloaded = await invoice_service.get_invoice(db_session, issued.id)
    assert reloaded is not None
    detail = await invoice_service.to_detail(db_session, reloaded)
    assert detail.vendor_identifiers[0].id_value == "BE0123456789"
    assert detail.payee is not None and detail.payee.bic == "GEBABEBB"
    assert detail.document_name == "Invoice"
    assert detail.currency_code == "EUR"
    assert detail.currency_minor_unit == 2


# --- voiding ---------------------------------------------------------------------


async def test_void_with_a_reason(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    issued = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )

    voided = await invoice_service.void(db_session, issued.id, "Wrong period", user.id)

    assert voided is not None
    assert voided.status == "void"
    assert voided.number == "INV-2026-0001"
    assert voided.void_reason == "Wrong period"
    assert voided.voided_by == user.id
    assert voided.voided_at is not None


async def test_only_an_issued_invoice_can_be_voided(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id)
    with pytest.raises(invoice_service.InvoiceNotIssuedError):
        await invoice_service.void(db_session, draft.id, None, user.id)

    issued = await _issue(db_session, draft, user.id)
    await invoice_service.void(db_session, issued.id, None, user.id)
    with pytest.raises(invoice_service.InvoiceNotIssuedError):
        await invoice_service.void(db_session, issued.id, None, user.id)


# --- issue preview ---------------------------------------------------------------


async def test_issue_preview(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    line = await add_service_line(db_session, project)
    consultant = await make_consultant(db_session)
    await log_hours(db_session, consultant, line, date(2026, 9, 2), 8)
    draft = await _draft(
        db_session,
        project,
        user.id,
        due_date="2026-10-01",
        period_start="2026-09-01",
        period_end="2026-09-30",
    )

    preview = await invoice_service.issue_preview(db_session, draft, OCT_14)

    assert preview.invoice_date == OCT_14
    assert preview.due_date == date(2026, 10, 1)
    assert preview.number == "INV-2026-0001"
    codes = {warning.code for warning in preview.warnings}
    assert {"due_before_invoice_date", "unlocked_hours", "no_payee_account"} <= codes
    assert preview.blocking == []


async def test_issue_preview_lists_what_blocks(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id, lines=[], payment_terms="net_30")
    project.status = "closed"
    await db_session.commit()

    preview = await invoice_service.issue_preview(db_session, draft, OCT_14)

    assert preview.due_date == date(2026, 11, 13)
    assert preview.blocking == ["project_not_active", "no_lines"]


# --- duplicating an issued invoice -----------------------------------------------


async def test_duplicate_of_an_issued_invoice_is_a_fresh_draft(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    issued = await _issue(
        db_session,
        await _draft(db_session, project, user.id, payment_terms="net_30", payee=PAYEE),
        user.id,
    )
    source = await invoice_service.get_invoice(db_session, issued.id)
    assert source is not None

    copy = await invoice_service.duplicate_invoice(db_session, source, user.id)

    assert copy.status == "draft"
    assert copy.number is None and copy.invoice_date is None and copy.issued_at is None
    assert copy.payment_terms == "net_30"
    assert copy.due_date is None
    assert copy.payee_account_identifier == "BE71096123456769"
    assert [line.description for line in copy.lines] == ["Work"]
    others = (
        (await db_session.execute(select(Invoice).where(Invoice.status == "draft")))
        .scalars()
        .all()
    )
    assert [invoice.id for invoice in others] == [copy.id]
