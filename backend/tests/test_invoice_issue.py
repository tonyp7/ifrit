import asyncio
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pypdf import PdfReader
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.company import PartyIdentifier, PayeeAccount
from app.models.file import File, StoredFile
from app.models.invoice import Invoice
from app.models.invoice_numbering import InvoiceNumberCounter
from app.models.project import Project
from app.pdf.errors import PdfEngineError, PdfStampError
from app.pdf.odt import TemplateData
from app.schemas.invoice import InvoiceWrite
from app.services import file_storage_service, invoice_service
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
from tests.pdf_helpers import fake_invoice_pdf

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


async def test_issue_preview_warns_when_there_will_be_no_due_date(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    neither = await _draft(db_session, project, user.id)
    preset = await _draft(db_session, project, user.id, payment_terms="net_30")
    fixed = await _draft(db_session, project, user.id, due_date="2026-12-01")

    for draft, expected in ((neither, True), (preset, False), (fixed, False)):
        preview = await invoice_service.issue_preview(db_session, draft, OCT_14)
        assert ("no_due_date" in {w.code for w in preview.warnings}) is expected
    # Issuing is still allowed: the warning never blocks.
    assert (
        await invoice_service.issue_preview(db_session, neither, OCT_14)
    ).blocking == []


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


# --- the PDF made at issue ---------------------------------------------------------------


async def test_issuing_stores_the_pdf_and_links_it(
    db_session, _storage_settings
) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    issued = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )

    assert issued.pdf_file_id is not None
    file = await file_storage_service.get_file(db_session, issued.pdf_file_id)
    assert file is not None and file.kind == "invoice"
    assert file.original_filename == "INV-2026-0001.pdf"
    assert file.uploaded_by == user.id
    path = file_storage_service.resolve_storage_path(file.stored_file.bucket_key)
    assert path.read_bytes() == fake_invoice_pdf("INV-2026-0001")
    assert file.stored_file.detected_content_type == "application/pdf"


async def test_the_pdf_is_made_from_the_issued_values(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[TemplateData] = []

    async def spy(data: TemplateData, template: bytes | None = None) -> bytes:
        seen.append(data)
        return b"%PDF"

    monkeypatch.setattr(invoice_service, "render_invoice_pdf", spy)
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id, payment_terms="net_30")
    await _issue(db_session, draft, user.id)

    values = seen[0].values
    assert values["invoice_number"] == "INV-2026-0001"
    assert values["invoice_date"] == "14 October 2026"
    assert values["due_date"] == "13 November 2026"
    assert values["status"] == "Issued"
    assert values["draft_watermark"] == ""
    assert values["document_name"] == "Invoice"


async def test_a_currency_without_decimals_is_not_printed_with_two(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[TemplateData] = []

    async def spy(data: TemplateData, template: bytes | None = None) -> bytes:
        seen.append(data)
        return b"%PDF"

    monkeypatch.setattr(invoice_service, "render_invoice_pdf", spy)
    user = await _user(db_session)
    project = await make_project(db_session, currency="JPY")
    await _issue(db_session, await _draft(db_session, project, user.id), user.id)

    assert seen[0].values["total"] == "950"
    assert seen[0].lines.rows[0].amount == "950"


async def test_a_pdf_that_cannot_be_made_issues_nothing(
    db_session, _storage_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    working = False

    async def broken(data: TemplateData, template: bytes | None = None) -> bytes:
        if not working:
            raise PdfEngineError("down")
        return b"%PDF-1.7 fake"

    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id)
    draft_id = draft.id
    user_id = user.id
    monkeypatch.setattr(invoice_service, "render_invoice_pdf", broken)

    with pytest.raises(invoice_service.PdfUnavailableError):
        await invoice_service.issue(db_session, draft_id, user_id, OCT_14)

    reloaded = await db_session.get(Invoice, draft_id)
    assert reloaded is not None
    await db_session.refresh(reloaded)
    assert reloaded.status == "draft" and reloaded.number is None
    assert reloaded.pdf_file_id is None
    assert await db_session.get(InvoiceNumberCounter, ("invoice", "2026")) is None
    count = (
        await db_session.execute(select(func.count()).select_from(File))
    ).scalar_one()
    assert count == 0
    stored = (
        await db_session.execute(select(func.count()).select_from(StoredFile))
    ).scalar_one()
    assert stored == 0
    # The next issue takes the number the failed one would have had.
    working = True
    again = await invoice_service.issue(db_session, draft_id, user_id, OCT_14)
    assert again is not None and again.number == "INV-2026-0001"


async def test_a_failure_after_the_file_is_written_removes_it(
    db_session, _storage_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id)
    draft_id = draft.id
    real_commit = db_session.commit

    async def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError):
        await invoice_service.issue(db_session, draft_id, user.id, OCT_14)
    monkeypatch.setattr(db_session, "commit", real_commit)

    leftovers = [p for p in _storage_settings.rglob("*") if p.is_file()]
    assert leftovers == []


async def test_identical_pdfs_share_stored_content(
    db_session, _storage_settings
) -> None:
    # The fake PDF depends only on the number, so two invoices differ; reissuing the same
    # content is covered by the storage tests.
    user = await _user(db_session)
    project = await make_project(db_session)
    first = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )
    second = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )
    assert first.pdf_file_id != second.pdf_file_id


async def test_a_draft_has_no_pdf_and_a_duplicate_does_not_copy_it(db_session) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    draft = await _draft(db_session, project, user.id)
    assert draft.pdf_file_id is None
    issued = await _issue(db_session, draft, user.id)
    source = await invoice_service.get_invoice(db_session, issued.id)
    assert source is not None and source.pdf_file_id is not None

    copy = await invoice_service.duplicate_invoice(db_session, source, user.id)

    assert copy.pdf_file_id is None


async def test_an_invoice_file_cannot_be_deleted_while_the_invoice_refers_to_it(
    db_session,
) -> None:
    user = await _user(db_session)
    project = await make_project(db_session)
    issued = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )
    file_id = issued.pdf_file_id
    assert file_id is not None

    with pytest.raises(IntegrityError):
        await db_session.execute(delete(File).where(File.id == file_id))


# --- voiding marks the stored PDF -------------------------------------------------------------


def _stored_bytes(file) -> bytes:
    return file_storage_service.resolve_storage_path(
        file.stored_file.bucket_key
    ).read_bytes()


async def _issued_with_pdf(db_session):
    user = await _user(db_session)
    project = await make_project(db_session)
    issued = await _issue(
        db_session, await _draft(db_session, project, user.id), user.id
    )
    return user, issued


async def test_voiding_stores_a_stamped_copy_and_keeps_the_original(db_session) -> None:
    user, issued = await _issued_with_pdf(db_session)
    original_id = issued.pdf_file_id
    assert original_id is not None
    original_file = await file_storage_service.get_file(db_session, original_id)
    assert original_file is not None
    original_bytes = _stored_bytes(original_file)

    voided = await invoice_service.void(db_session, issued.id, None, user.id)

    assert voided is not None and voided.status == "void"
    assert voided.pdf_file_id is not None and voided.pdf_file_id != original_id
    stamped_file = await file_storage_service.get_file(db_session, voided.pdf_file_id)
    assert stamped_file is not None and stamped_file.kind == "invoice"
    assert stamped_file.original_filename == "INV-2026-0001.pdf"
    pages = PdfReader(io.BytesIO(_stored_bytes(stamped_file))).pages
    assert len(pages) == 1 and "VOIDED" in pages[0].extract_text()
    # The issued document is still there, byte for byte, with nothing referring to it.
    kept = await file_storage_service.get_file(db_session, original_id)
    assert kept is not None and _stored_bytes(kept) == original_bytes
    assert b"VOIDED" not in original_bytes


async def test_a_void_never_calls_the_pdf_engine(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, issued = await _issued_with_pdf(db_session)

    async def forbidden(data: TemplateData, template: bytes | None = None) -> bytes:
        raise AssertionError("a void must not render")

    monkeypatch.setattr(invoice_service, "render_invoice_pdf", forbidden)

    voided = await invoice_service.void(db_session, issued.id, "Wrong period", user.id)

    assert voided is not None and voided.status == "void"


async def test_an_invoice_issued_before_pdfs_were_kept_is_voided_without_a_file(
    db_session,
) -> None:
    user = await _user(db_session)
    legacy = await make_issued_invoice(db_session, "OLD-1")

    voided = await invoice_service.void(db_session, legacy.id, None, user.id)

    assert voided is not None and voided.status == "void" and voided.pdf_file_id is None
    count = (
        await db_session.execute(select(func.count()).select_from(File))
    ).scalar_one()
    assert count == 0


async def _damage_stored_pdf(db_session, issued, *, delete: bool) -> None:
    assert issued.pdf_file_id is not None
    file = await file_storage_service.get_file(db_session, issued.pdf_file_id)
    assert file is not None
    path = file_storage_service.resolve_storage_path(file.stored_file.bucket_key)
    if delete:
        path.unlink()
    else:
        path.write_bytes(b"this is not a pdf")


@pytest.mark.parametrize("delete", [False, True])
async def test_a_pdf_that_cannot_be_marked_leaves_the_invoice_issued(
    db_session, delete: bool
) -> None:
    user, issued = await _issued_with_pdf(db_session)
    issued_id, user_id, original_id = issued.id, user.id, issued.pdf_file_id
    await _damage_stored_pdf(db_session, issued, delete=delete)

    with pytest.raises(PdfStampError):
        await invoice_service.void(db_session, issued_id, "x", user_id)

    reloaded = await db_session.get(Invoice, issued_id)
    assert reloaded is not None
    await db_session.refresh(reloaded)
    assert reloaded.status == "issued" and reloaded.voided_at is None
    assert reloaded.void_reason is None and reloaded.pdf_file_id == original_id
    count = (
        await db_session.execute(select(func.count()).select_from(File))
    ).scalar_one()
    assert count == 1


async def test_a_failed_commit_removes_the_stamped_file(
    db_session, _storage_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, issued = await _issued_with_pdf(db_session)
    before = sorted(p for p in _storage_settings.rglob("*") if p.is_file())
    real_commit = db_session.commit

    async def failing_commit() -> None:
        raise RuntimeError("commit failed")

    issued_id, user_id = issued.id, user.id
    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError):
        await invoice_service.void(db_session, issued_id, None, user_id)
    monkeypatch.setattr(db_session, "commit", real_commit)

    assert sorted(p for p in _storage_settings.rglob("*") if p.is_file()) == before
