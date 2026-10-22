import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import ColumnElement, delete, func, literal, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import server_today
from app.models.company import Company, PartyIdentifier, PayeeAccount
from app.models.currency import Currency
from app.models.invoice import (
    Invoice,
    InvoiceLine,
    InvoiceReference,
    InvoiceStatus,
    InvoiceTax,
    TaxBaseMode,
)
from app.models.project import BillingMilestone, Project, ProjectType, ServiceLine
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.pdf.errors import PdfError, PdfStampError
from app.pdf.http import pdf_filename
from app.pdf.render import render_invoice_pdf
from app.pdf.stamp import stamp_voided
from app.pdf.values import build_template_data
from app.schemas.company import BankAddress
from app.schemas.invoice import (
    BillingContext,
    BlockingReason,
    ContextAddress,
    ContextCompany,
    ContextMilestone,
    ContextPayeeAccount,
    ContextServiceLine,
    GeneratedLine,
    GenerateMilestoneRequest,
    GenerateRequest,
    GenerateResponse,
    GenerateTimeRequest,
    InvoiceableProject,
    InvoiceDetail,
    InvoiceLineOut,
    InvoiceLineWrite,
    InvoicePayeeOut,
    InvoicePayeeWrite,
    InvoiceReferenceOut,
    InvoiceTaxOut,
    InvoiceTaxWrite,
    InvoiceWarning,
    InvoiceWrite,
    IssuePreview,
    OmittedServiceLine,
    PartyOut,
    PartyWrite,
    SnapshotIdentifier,
    UnlockedServiceLine,
)
from app.schemas.project import ProjectReferenceWrite
from app.services import app_settings, file_storage_service, invoice_numbering_service
from app.services.invoice_template_service import resolve_template
from app.services.payment_terms import apply_payment_terms
from app.services.sorting import resolve_sort

logger = logging.getLogger(__name__)

PAGE_SIZE = 50
INVOICEABLE_TYPES: tuple[ProjectType, ...] = (
    "time_and_material",
    "capped_tm",
    "fixed_price",
)
# Billed from the hours logged; Fixed Price is billed from its milestones instead.
TIME_BASED_TYPES: tuple[ProjectType, ...] = ("time_and_material", "capped_tm")
_ADDRESS_FIELDS = (
    "line1",
    "line2",
    "line3",
    "city",
    "postal_zone",
    "country_subdivision",
    "country_code",
)
_QUANTITY_QUANTUM = Decimal("0.00001")
_RATE_QUANTUM = Decimal("0.001")
# NUMERIC(12, 3): a rate worked back from an amount on a tiny base can be too large to store,
# and then counts as one that cannot be worked out.
_RATE_LIMIT = Decimal(10) ** 9


class ProjectNotInvoiceableError(Exception):
    """The project cannot have a new invoice: deleted, not Active, or of a type that is not
    invoiced."""


class InvoiceNotDraftError(Exception):
    pass


class InvoiceNotIssuedError(Exception):
    """Only an issued invoice can be voided."""


class ProjectNotActiveError(Exception):
    """A draft cannot be issued while its project is not Active, or has been deleted."""


class NoLinesError(Exception):
    """An invoice with no line cannot be issued."""


class NumberAlreadyUsedError(Exception):
    """The number the counter rendered already belongs to another invoice."""

    def __init__(self, number: str) -> None:
        super().__init__(number)
        self.number = number


class PdfUnavailableError(Exception):
    """The invoice's PDF could not be made, so nothing was issued."""


class InvalidInvoiceDataError(Exception):
    """A value refers to something that does not fit: a service line or milestone of another
    project, an unknown currency."""


def money_round(value: Decimal, minor_unit: int | None) -> Decimal:
    """Rounds to the currency's minor unit (2 when it has none defined), half away from
    zero, the usual commercial rule. ROUND_HALF_UP on Decimal rounds away from zero for
    negative amounts too, so a discount rounds like the charge it offsets."""
    places = 2 if minor_unit is None else minor_unit
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TaxInput:
    """What decides a tax row's numbers: its Applies to choice and the value typed last."""

    base_mode: TaxBaseMode
    rate: Decimal | None
    amount: Decimal | None
    amount_set_by_hand: bool


@dataclass(frozen=True)
class ComputedTax:
    base_mode: TaxBaseMode
    rate: Decimal | None
    amount: Decimal
    base_amount: Decimal


def compute_taxes(
    subtotal: Decimal, rows: list[TaxInput], minor_unit: int | None
) -> list[ComputedTax]:
    """Works out each tax row in order. A row's base is the subtotal, or for a compounding
    row the subtotal plus every amount above it. A rate-driven row's amount is base x rate,
    rounded to the currency; a hand-set row keeps its amount and its rate is worked back to
    3 decimals, or left unknown on a zero base. The form runs the very same rules, so what it
    shows is what gets stored."""
    computed: list[ComputedTax] = []
    above = Decimal(0)
    for position, row in enumerate(rows):
        # On the first row there is nothing above, so both choices give the same base.
        mode: TaxBaseMode = "subtotal" if position == 0 else row.base_mode
        base = subtotal + above if mode == "cumulative" else subtotal
        if row.amount_set_by_hand:
            amount = row.amount if row.amount is not None else Decimal(0)
            rate: Decimal | None = None
            if base != 0:
                rate = (amount / base * 100).quantize(
                    _RATE_QUANTUM, rounding=ROUND_HALF_UP
                )
                if abs(rate) >= _RATE_LIMIT:
                    rate = None
        else:
            rate = row.rate if row.rate is not None else Decimal(0)
            amount = money_round(base * rate / 100, minor_unit)
        computed.append(
            ComputedTax(base_mode=mode, rate=rate, amount=amount, base_amount=base)
        )
        above += amount
    return computed


def _tax_input(tax: InvoiceTaxWrite | InvoiceTax) -> TaxInput:
    return TaxInput(
        base_mode=tax.base_mode,
        rate=tax.rate,
        amount=tax.amount,
        amount_set_by_hand=tax.amount_set_by_hand,
    )


def _apply_taxes(
    invoice: Invoice,
    labels: list[str],
    inputs: list[TaxInput],
    minor_unit: int | None,
) -> None:
    """Replaces the invoice's tax rows from `inputs` and sets its total. Expects the
    subtotal to be up to date."""
    computed = compute_taxes(invoice.subtotal, inputs, minor_unit)
    invoice.taxes = [
        InvoiceTax(
            position=position,
            label=label,
            base_mode=result.base_mode,
            rate=result.rate,
            amount=result.amount,
            amount_set_by_hand=row.amount_set_by_hand,
            base_amount=result.base_amount,
        )
        for position, (label, row, result) in enumerate(
            zip(labels, inputs, computed, strict=True)
        )
    ]
    invoice.total = invoice.subtotal + sum(
        (result.amount for result in computed), Decimal(0)
    )


def _hours(duration: timedelta) -> Decimal:
    return Decimal(int(duration.total_seconds())) / Decimal(3600)


async def _minor_unit(db: AsyncSession, currency_code: str) -> int | None:
    currency = await db.get(Currency, currency_code)
    return currency.minor_unit if currency is not None else None


def is_invoiceable(project: Project) -> bool:
    return (
        project.is_active
        and project.status == "active"
        and project.project_type in INVOICEABLE_TYPES
    )


def _display_name(company: Company) -> str:
    return company.trading_name or company.legal_name


# --- reading the project for the form --------------------------------------------


async def list_projects(
    db: AsyncSession, search: str | None, invoiced: bool
) -> list[InvoiceableProject]:
    """Without `invoiced`, the projects a new invoice can be started for. With it, every
    project that has at least one invoice, whatever its state, for the list's filter."""
    client = func.coalesce(Company.trading_name, Company.legal_name)
    filters: list[ColumnElement[bool]] = []
    if invoiced:
        filters.append(
            select(Invoice.id).where(Invoice.project_id == Project.id).exists()
        )
    else:
        filters += [
            Project.is_active.is_(True),
            Project.status == "active",
            Project.project_type.in_(INVOICEABLE_TYPES),
        ]
    if search:
        filters.append(Project.name.ilike(f"%{search}%"))
    rows = (
        await db.execute(
            select(Project, client)
            .outerjoin(Company, Project.client_company_id == Company.id)
            .where(*filters)
            .order_by(Project.name, Project.id)
        )
    ).all()
    return [
        InvoiceableProject(
            id=project.id,
            name=project.name,
            project_type=project.project_type,
            status=project.status,
            client_name=client_name,
            currency_code=project.invoicing_currency,
        )
        for project, client_name in rows
    ]


async def _load_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    return (
        await db.execute(
            select(Project)
            .options(
                selectinload(Project.service_lines),
                selectinload(Project.billing_milestones),
                selectinload(Project.project_references),
                selectinload(Project.vendor_company).selectinload(Company.addresses),
                selectinload(Project.vendor_company).selectinload(
                    Company.payee_accounts
                ),
                selectinload(Project.client_company).selectinload(Company.addresses),
            )
            .where(Project.id == project_id)
        )
    ).scalar_one_or_none()


def _context_company(company: Company | None) -> ContextCompany | None:
    if company is None:
        return None
    return ContextCompany(
        id=company.id,
        display_name=_display_name(company),
        is_active=company.is_active,
        addresses=[
            ContextAddress(
                id=address.id,
                address_type=address.address_type,
                line1=address.line1,
                line2=address.line2,
                line3=address.line3,
                city=address.city,
                postal_zone=address.postal_zone,
                country_subdivision=address.country_subdivision,
                country_code=address.country_code,
                is_primary=address.is_primary,
            )
            for address in company.addresses
        ],
    )


async def billing_context(
    db: AsyncSession, project_id: uuid.UUID
) -> BillingContext | None:
    """None for a deleted or unknown project."""
    project = await _load_project(db, project_id)
    if project is None or not project.is_active:
        return None
    vendor = project.vendor_company
    accounts: list[PayeeAccount] = vendor.payee_accounts if vendor is not None else []
    return BillingContext(
        id=project.id,
        name=project.name,
        project_type=project.project_type,
        status=project.status,
        is_active=project.is_active,
        currency_code=project.invoicing_currency,
        currency_minor_unit=await _minor_unit(db, project.invoicing_currency),
        vendor=_context_company(vendor),
        client=_context_company(project.client_company),
        payee_accounts=[
            ContextPayeeAccount(
                id=account.id,
                is_primary=account.is_primary,
                payment_means_code=account.payment_means_code,
                account_scheme=account.account_scheme,
                account_identifier=account.account_identifier,
                account_name=account.account_name,
                currency_code=account.currency_code,
                bic=account.bic,
                bank_name=account.bank_name,
                bank_address=_bank_address(account, "bank"),
            )
            for account in sorted(
                accounts, key=lambda a: (not a.is_primary, a.currency_code, str(a.id))
            )
        ],
        service_lines=[
            ContextServiceLine(
                id=line.id, name=line.name, uom=line.uom, unit_price=line.unit_price
            )
            for line in project.service_lines
            if line.is_active
        ],
        # A project that changed type away from Fixed Price has none left anyway; the
        # check keeps the context to what the form will actually offer.
        milestones=[
            ContextMilestone(
                id=milestone.id,
                description=milestone.description,
                due_date=milestone.due_date,
                value=milestone.value,
            )
            for milestone in project.billing_milestones
        ]
        if project.project_type == "fixed_price"
        else [],
        references=[
            InvoiceReferenceOut(kind=ref.kind, label=ref.label, value=ref.value)
            for ref in sorted(project.project_references, key=lambda r: r.position)
        ],
    )


# --- generation ------------------------------------------------------------------


async def _unlocked_days(
    db: AsyncSession, service_line_ids: list[uuid.UUID], start: date, end: date
) -> dict[uuid.UUID, int]:
    """Days per service line that still have an unlocked, non-zero entry in the period:
    the amounts billed for them could still change after the invoice goes out."""
    rows = (
        await db.execute(
            select(TimeEntry.service_line_id, func.count(func.distinct(TimeEntry.date)))
            .where(
                TimeEntry.service_line_id.in_(service_line_ids),
                TimeEntry.date.between(start, end),
                TimeEntry.is_locked.is_(False),
                TimeEntry.time_entry > timedelta(0),
            )
            .group_by(TimeEntry.service_line_id)
        )
    ).all()
    return {line_id: count for line_id, count in rows}


def _unlocked_warning(
    lines: list[ServiceLine], days: dict[uuid.UUID, int]
) -> list[InvoiceWarning]:
    flagged = [
        UnlockedServiceLine(
            name=line.name, uom=line.uom, unit_price=line.unit_price, days=days[line.id]
        )
        for line in lines
        if days.get(line.id)
    ]
    return (
        [InvoiceWarning(code="unlocked_hours", service_lines=flagged)]
        if flagged
        else []
    )


async def generate_lines(db: AsyncSession, data: GenerateRequest) -> GenerateResponse:
    if isinstance(data, GenerateMilestoneRequest):
        return await generate_milestone_lines(db, data)
    return await generate_tm_lines(db, data)


async def _generating_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if project is None or not project.is_active:
        raise InvalidInvoiceDataError("Project not found")
    return project


async def generate_milestone_lines(
    db: AsyncSession, data: GenerateMilestoneRequest
) -> GenerateResponse:
    """One line copied from each milestone. Nothing links back to them, so a milestone can
    later be edited or deleted without the invoice changing. Saves nothing."""
    project = await _generating_project(db, data.project_id)
    if project.project_type != "fixed_price":
        raise InvalidInvoiceDataError("Only Fixed Price projects bill milestones")
    wanted = set(data.milestone_ids)
    milestones = (
        (
            await db.execute(
                select(BillingMilestone)
                .where(
                    BillingMilestone.id.in_(wanted),
                    BillingMilestone.project_id == project.id,
                )
                # The contract's order, as the project lists them, not the order they
                # were ticked in.
                .order_by(BillingMilestone.position, BillingMilestone.created_at)
            )
        )
        .scalars()
        .all()
    )
    if len(milestones) != len(wanted):
        raise InvalidInvoiceDataError("Every milestone must belong to the project")
    return GenerateResponse(
        lines=[
            GeneratedLine(
                name=milestone.description,
                quantity=Decimal(1),
                uom="ea",
                unit_price=milestone.value,
            )
            for milestone in milestones
        ],
        omitted=[],
        warnings=[],
    )


async def generate_tm_lines(
    db: AsyncSession, data: GenerateTimeRequest
) -> GenerateResponse:
    """Previews the lines for the selected service lines and period. Saves nothing and
    never locks or unlocks an entry: locking belongs to the timesheet."""
    project = await _generating_project(db, data.project_id)
    if project.project_type not in TIME_BASED_TYPES:
        raise InvalidInvoiceDataError("Only Time & Material projects bill hours")

    selected = (
        (
            await db.execute(
                select(ServiceLine).where(
                    ServiceLine.id.in_(data.service_line_ids),
                    ServiceLine.project_id == project.id,
                    ServiceLine.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {line.id: line for line in selected}
    if set(data.service_line_ids) != by_id.keys():
        raise InvalidInvoiceDataError(
            "Every service line must be an active line of the project"
        )
    # Keep the order the lines were asked for in.
    ordered = [by_id[line_id] for line_id in dict.fromkeys(data.service_line_ids)]

    # Every entry counts, locked or not, whoever logged it, deactivated consultants
    # included: they did the work.
    total_rows = (
        await db.execute(
            select(TimeEntry.service_line_id, func.sum(TimeEntry.time_entry))
            .where(
                TimeEntry.service_line_id.in_(by_id.keys()),
                TimeEntry.date.between(data.period_start, data.period_end),
            )
            .group_by(TimeEntry.service_line_id)
        )
    ).all()
    totals: dict[uuid.UUID, timedelta] = {
        line_id: total for line_id, total in total_rows
    }
    general = await app_settings.get_group(db, "general")
    workday_hours = Decimal(general.model_dump()["standard_workday_seconds"]) / Decimal(
        3600
    )

    lines: list[GeneratedLine] = []
    omitted: list[OmittedServiceLine] = []
    warnings: list[InvoiceWarning] = []
    for line in ordered:
        if line.uom == "ea":
            # An "each" line is not time-based: there is nothing to convert, so it comes
            # out empty for the user to fill in, and is warned about.
            lines.append(
                GeneratedLine(
                    name=line.name,
                    quantity=Decimal(0),
                    uom="ea",
                    unit_price=line.unit_price,
                )
            )
            continue
        hours = _hours(totals.get(line.id) or timedelta(0))
        if hours == 0:
            omitted.append(
                OmittedServiceLine(
                    service_line_id=line.id,
                    name=line.name,
                    uom=line.uom,
                    unit_price=line.unit_price,
                )
            )
            continue
        quantity = hours if line.uom == "hours" else hours / workday_hours
        lines.append(
            GeneratedLine(
                name=line.name,
                quantity=quantity.quantize(_QUANTITY_QUANTUM, rounding=ROUND_HALF_UP),
                uom=line.uom,
                unit_price=line.unit_price,
            )
        )

    if any(line.quantity == 0 for line in lines):
        warnings.append(InvoiceWarning(code="zero_quantity"))
    days = await _unlocked_days(db, list(by_id), data.period_start, data.period_end)
    warnings += _unlocked_warning(ordered, days)
    return GenerateResponse(lines=lines, omitted=omitted, warnings=warnings)


# --- writing drafts --------------------------------------------------------------


def _set_party(invoice: Invoice, prefix: str, party: PartyWrite) -> None:
    setattr(invoice, f"{prefix}_name", party.name)
    address: dict[str, Any] = party.address.model_dump() if party.address else {}
    for field in _ADDRESS_FIELDS:
        setattr(invoice, f"{prefix}_{field}", address.get(field))


def _set_payee(invoice: Invoice, payee: InvoicePayeeWrite | None) -> None:
    values: dict[str, Any] = payee.model_dump(exclude={"bank_address"}) if payee else {}
    for field in (
        "payment_means_code",
        "account_scheme",
        "account_identifier",
        "account_name",
        "currency_code",
        "bic",
        "bank_name",
    ):
        setattr(invoice, f"payee_{field}", values.get(field))
    bank: dict[str, Any] = {}
    if payee is not None and payee.bank_address is not None:
        bank = payee.bank_address.model_dump()
    for field in _ADDRESS_FIELDS:
        setattr(invoice, f"payee_bank_{field}", bank.get(field))


async def _check_payee_currency(
    db: AsyncSession, payee: InvoicePayeeWrite | None
) -> None:
    # Any ISO 4217 code will do, enabled or not, so a copy outlives a disabled currency.
    if payee is not None and await db.get(Currency, payee.currency_code) is None:
        raise InvalidInvoiceDataError("The payee currency is not an ISO 4217 currency")


async def _apply(
    db: AsyncSession, invoice: Invoice, data: InvoiceWrite, project: Project
) -> None:
    """Writes every draft field from `data`, replaces the lines, references and tax rows,
    and recomputes the stored amounts. The currency always follows the project."""
    await _check_payee_currency(db, data.payee)
    minor = await _minor_unit(db, project.invoicing_currency)
    places = 2 if minor is None else minor
    for tax in data.taxes:
        # A typed amount cannot have more decimals than the money it is paid in.
        if tax.amount_set_by_hand and tax.amount is not None:
            exponent = tax.amount.normalize().as_tuple().exponent
            if isinstance(exponent, int) and -exponent > places:
                raise InvalidInvoiceDataError(
                    f"A tax amount can have at most {places} decimals in this currency"
                )
    invoice.project_id = project.id
    invoice.currency_code = project.invoicing_currency
    _set_party(invoice, "bill_from", data.bill_from)
    _set_party(invoice, "bill_to", data.bill_to)
    # A Fixed Price invoice bills a milestone, not a stretch of time: whatever period the
    # client sends (say, one left over from before the project changed type) would only
    # mislead whoever reads the invoice.
    fixed_price = project.project_type == "fixed_price"
    invoice.period_start = None if fixed_price else data.period_start
    invoice.period_end = None if fixed_price else data.period_end
    invoice.payment_terms = data.payment_terms
    invoice.due_date = data.due_date
    _set_payee(invoice, data.payee)

    invoice.lines = [
        InvoiceLine(
            position=position,
            description=line.description,
            quantity=line.quantity,
            uom=line.uom,
            unit_price=line.unit_price,
            amount=money_round(line.quantity * line.unit_price, minor),
        )
        for position, line in enumerate(data.lines)
    ]
    invoice.references = [
        InvoiceReference(
            position=position, kind=ref.kind, label=ref.label, value=ref.value
        )
        for position, ref in enumerate(data.references)
    ]
    invoice.subtotal = sum((line.amount for line in invoice.lines), Decimal(0))
    _apply_taxes(
        invoice,
        [tax.label for tax in data.taxes],
        [_tax_input(tax) for tax in data.taxes],
        minor,
    )


async def create_invoice(
    db: AsyncSession, data: InvoiceWrite, user_id: uuid.UUID
) -> Invoice:
    project = await db.get(Project, data.project_id)
    if project is None or not is_invoiceable(project):
        raise ProjectNotInvoiceableError()
    invoice = Invoice(
        status="draft", created_by=user_id, lines=[], references=[], taxes=[]
    )
    await _apply(db, invoice, data, project)
    db.add(invoice)
    await db.commit()
    return invoice


@dataclass
class DraftPdfInput:
    """What a PDF of a draft is made from. The invoice is never added to the session."""

    invoice: Invoice
    minor_unit: int
    document_name: str
    vendor_identifiers: list[dict[str, Any]]
    client_identifiers: list[dict[str, Any]]


async def draft_pdf_input(db: AsyncSession, data: InvoiceWrite) -> DraftPdfInput:
    """A draft as `data` describes it, for a PDF preview: built by the same code a save runs,
    so its amounts and its rejections are a save's, but never added to the session, so
    nothing is written."""
    project = await db.get(Project, data.project_id)
    if project is None or not is_invoiceable(project):
        raise ProjectNotInvoiceableError()
    invoice = Invoice(
        status="draft", created_by=None, lines=[], references=[], taxes=[]
    )
    await _apply(db, invoice, data, project)
    return await _draft_pdf_input(db, invoice, project)


async def saved_draft_pdf_input(db: AsyncSession, invoice: Invoice) -> DraftPdfInput:
    """A saved draft, for its PDF."""
    project = await db.get(Project, invoice.project_id)
    if project is None:
        raise ProjectNotInvoiceableError()
    return await _draft_pdf_input(db, invoice, project)


async def _draft_pdf_input(
    db: AsyncSession, invoice: Invoice, project: Project
) -> DraftPdfInput:
    minor = await _minor_unit(db, project.invoicing_currency)
    today = server_today()
    document_name = (await app_settings.get_group(db, "invoicing")).model_dump()[
        "document_name"
    ]
    return DraftPdfInput(
        invoice=invoice,
        minor_unit=2 if minor is None else minor,
        document_name=document_name,
        vendor_identifiers=await _identifiers(db, project.vendor_company_id, today),
        client_identifiers=await _identifiers(db, project.client_company_id, today),
    )


async def stored_pdf(db: AsyncSession, invoice: Invoice) -> bytes | None:
    """The bytes kept when the invoice was issued, or None when it has none. A file missing
    from the disk, or recorded outside the storage root, is raised for the caller to log."""
    if invoice.pdf_file_id is None:
        return None
    file = await file_storage_service.get_file(db, invoice.pdf_file_id)
    if file is None:
        return None
    path = file_storage_service.resolve_storage_path(file.stored_file.bucket_key)
    return await asyncio.to_thread(path.read_bytes)


async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice | None:
    return (
        await db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.references),
                selectinload(Invoice.taxes),
                selectinload(Invoice.project),
            )
            .where(Invoice.id == invoice_id)
        )
    ).scalar_one_or_none()


async def update_invoice(
    db: AsyncSession, invoice: Invoice, data: InvoiceWrite
) -> Invoice:
    if invoice.status != "draft":
        raise InvoiceNotDraftError()
    project = await db.get(Project, data.project_id)
    if project is None:
        raise ProjectNotInvoiceableError()
    # A draft may keep a project that has since been closed or deleted; moving it to
    # another project is starting anew, so that project must be invoiceable.
    if project.id != invoice.project_id and not is_invoiceable(project):
        raise ProjectNotInvoiceableError()
    await _apply(db, invoice, data, project)
    await db.commit()
    return invoice


async def delete_invoice(db: AsyncSession, invoice: Invoice) -> None:
    if invoice.status != "draft":
        raise InvoiceNotDraftError()
    # A draft has no number and nothing refers to it, so removing it (its lines and
    # references cascade) loses nothing.
    await db.execute(delete(Invoice).where(Invoice.id == invoice.id))
    await db.commit()


def to_write(invoice: Invoice) -> InvoiceWrite:
    """The invoice's own content as a write payload, for duplicating it."""
    return InvoiceWrite(
        project_id=invoice.project_id,
        bill_from=PartyWrite(
            name=invoice.bill_from_name, address=_bank_address(invoice, "bill_from")
        ),
        bill_to=PartyWrite(
            name=invoice.bill_to_name, address=_bank_address(invoice, "bill_to")
        ),
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        payment_terms=invoice.payment_terms,
        due_date=None if invoice.payment_terms is not None else invoice.due_date,
        payee=_payee_write(invoice),
        references=[
            ProjectReferenceWrite(kind=ref.kind, label=ref.label, value=ref.value)
            for ref in invoice.references
        ],
        lines=[
            InvoiceLineWrite(
                description=line.description,
                quantity=line.quantity,
                uom=line.uom,
                unit_price=line.unit_price,
            )
            for line in invoice.lines
        ],
        taxes=[
            InvoiceTaxWrite(
                label=tax.label,
                base_mode=tax.base_mode,
                rate=tax.rate,
                amount=tax.amount,
                amount_set_by_hand=tax.amount_set_by_hand,
            )
            for tax in invoice.taxes
        ],
    )


async def duplicate_invoice(
    db: AsyncSession, invoice: Invoice, user_id: uuid.UUID
) -> Invoice:
    """A new draft with the source's content. Created even when the project can no longer
    take a new invoice: the copy is a starting point, and issuing it is what is refused."""
    project = await db.get(Project, invoice.project_id)
    if project is None:
        raise ProjectNotInvoiceableError()
    copy = Invoice(
        status="draft", created_by=user_id, lines=[], references=[], taxes=[]
    )
    await _apply(db, copy, to_write(invoice), project)
    db.add(copy)
    await db.commit()
    return copy


# --- reading invoices ------------------------------------------------------------


def _bank_address(obj: Any, prefix: str) -> BankAddress | None:
    line1 = getattr(obj, f"{prefix}_line1")
    if line1 is None:
        return None
    return BankAddress(
        **{field: getattr(obj, f"{prefix}_{field}") for field in _ADDRESS_FIELDS}
    )


def _payee_out(invoice: Invoice) -> InvoicePayeeOut | None:
    if invoice.payee_payment_means_code is None:
        return None
    return InvoicePayeeOut(
        payment_means_code=invoice.payee_payment_means_code,
        account_scheme=invoice.payee_account_scheme or "other",
        account_identifier=invoice.payee_account_identifier or "",
        account_name=invoice.payee_account_name,
        currency_code=invoice.payee_currency_code or "",
        bic=invoice.payee_bic,
        bank_name=invoice.payee_bank_name,
        bank_address=_bank_address(invoice, "payee_bank"),
    )


def _payee_write(invoice: Invoice) -> InvoicePayeeWrite | None:
    payee = _payee_out(invoice)
    return InvoicePayeeWrite(**payee.model_dump()) if payee is not None else None


async def invoice_warnings(db: AsyncSession, invoice: Invoice) -> list[InvoiceWarning]:
    """The warnings of the invoice as saved. Lines keep no link to their service line, so
    unlocked hours are checked across every service line of the project in the period."""
    warnings: list[InvoiceWarning] = []
    project = await _load_project(db, invoice.project_id)
    if invoice.period_start is not None and invoice.period_end is not None and project:
        lines = list(project.service_lines)
        days = await _unlocked_days(
            db, [line.id for line in lines], invoice.period_start, invoice.period_end
        )
        warnings += _unlocked_warning(lines, days)
    if any(line.quantity == 0 for line in invoice.lines):
        warnings.append(InvoiceWarning(code="zero_quantity"))
    if any(tax.amount_set_by_hand and tax.rate is None for tax in invoice.taxes):
        warnings.append(InvoiceWarning(code="tax_rate_not_derivable"))
    if invoice.subtotal < 0:
        warnings.append(InvoiceWarning(code="negative_subtotal"))
    if invoice.payee_payment_means_code is None:
        warnings.append(InvoiceWarning(code="no_payee_account"))
    elif invoice.payee_currency_code != invoice.currency_code:
        warnings.append(InvoiceWarning(code="payee_currency"))
    # Neither a preset nor a fixed date means the issued invoice prints no due date at all.
    if not invoice.payment_terms and invoice.due_date is None:
        warnings.append(InvoiceWarning(code="no_due_date"))
    if project is not None:
        inactive: list[Any] = []
        if project.vendor_company is not None and not project.vendor_company.is_active:
            inactive.append("vendor")
        if project.client_company is not None and not project.client_company.is_active:
            inactive.append("client")
        if inactive:
            warnings.append(InvoiceWarning(code="inactive_company", companies=inactive))
    return warnings


async def to_detail(db: AsyncSession, invoice: Invoice) -> InvoiceDetail:
    return InvoiceDetail(
        id=invoice.id,
        status=invoice.status,
        project_id=invoice.project_id,
        project_name=invoice.project.name,
        currency_code=invoice.currency_code,
        # Once issued, the decimals are those frozen at issue, not the currency's now.
        currency_minor_unit=(
            invoice.currency_minor_unit
            if invoice.status != "draft"
            else await _minor_unit(db, invoice.currency_code)
        ),
        bill_from=PartyOut(
            name=invoice.bill_from_name, address=_bank_address(invoice, "bill_from")
        ),
        bill_to=PartyOut(
            name=invoice.bill_to_name, address=_bank_address(invoice, "bill_to")
        ),
        period_start=invoice.period_start,
        period_end=invoice.period_end,
        payment_terms=invoice.payment_terms,
        due_date=invoice.due_date,
        payee=_payee_out(invoice),
        references=[
            InvoiceReferenceOut(kind=ref.kind, label=ref.label, value=ref.value)
            for ref in invoice.references
        ],
        lines=[
            InvoiceLineOut(
                description=line.description,
                quantity=line.quantity,
                uom=line.uom,
                unit_price=line.unit_price,
                amount=line.amount,
            )
            for line in invoice.lines
        ],
        subtotal=invoice.subtotal,
        taxes=[
            InvoiceTaxOut(
                label=tax.label,
                base_mode=tax.base_mode,
                rate=tax.rate,
                amount=tax.amount,
                amount_set_by_hand=tax.amount_set_by_hand,
                base_amount=tax.base_amount,
            )
            for tax in invoice.taxes
        ],
        total=invoice.total,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        # An issued invoice is not being prepared any more: nothing to warn about.
        warnings=await invoice_warnings(db, invoice)
        if invoice.status == "draft"
        else [],
        number=invoice.number,
        invoice_date=invoice.invoice_date,
        document_name=invoice.document_name,
        vendor_identifiers=[
            SnapshotIdentifier(**i) for i in invoice.vendor_identifiers or []
        ],
        client_identifiers=[
            SnapshotIdentifier(**i) for i in invoice.client_identifiers or []
        ],
        issued_at=invoice.issued_at,
        issued_by_name=await _user_name(db, invoice.issued_by),
        voided_at=invoice.voided_at,
        voided_by_name=await _user_name(db, invoice.voided_by),
        void_reason=invoice.void_reason,
        has_pdf=invoice.pdf_file_id is not None,
    )


async def _user_name(db: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    user = await db.get(User, user_id) if user_id is not None else None
    return user.full_name if user is not None else None


async def list_invoices(
    db: AsyncSession,
    page: int,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    project_id: uuid.UUID | None = None,
    statuses: list[InvoiceStatus] | None = None,
    search: str | None = None,
) -> tuple[list[tuple[Invoice, str, int | None, str | None]], int]:
    """(invoice, project name, currency minor unit, lines summary) rows, newest first by
    default. Void invoices are left out unless asked for: they are kept as
    evidence, not worked on. `search` keeps the invoices whose number, project, Bill To name
    or any line description contains it, in any letter case."""
    sortable_columns = {
        "created_at": Invoice.created_at,
        "project": Project.name,
        "client": Invoice.bill_to_name,
        "billed_for": Invoice.period_start,
        "status": Invoice.status,
        "total": Invoice.total,
        "due": Invoice.due_date,
        "number": Invoice.number,
        "issued": Invoice.invoice_date,
    }
    filters: list[ColumnElement[bool]] = [
        Invoice.status.in_(statuses if statuses else ("draft", "issued"))
    ]
    if project_id is not None:
        filters.append(Invoice.project_id == project_id)
    if search and search.strip():
        # `autoescape` makes a typed % or _ match itself instead of acting as a wildcard.
        text = search.strip()
        # EXISTS rather than a join to the lines, so an invoice with two matching lines is
        # still one row and one in the count.
        line_matches = (
            select(literal(1))
            .where(
                InvoiceLine.invoice_id == Invoice.id,
                InvoiceLine.description.icontains(text, autoescape=True),
            )
            .exists()
        )
        filters.append(
            or_(
                Invoice.number.icontains(text, autoescape=True),
                Project.name.icontains(text, autoescape=True),
                Invoice.bill_to_name.icontains(text, autoescape=True),
                line_matches,
            )
        )
    # The project name is part of the search, so the count joins the project exactly as the
    # rows do: both use the same filters and cannot disagree about the pages.
    total = (
        await db.execute(
            select(func.count())
            .select_from(Invoice)
            .join(Project, Invoice.project_id == Project.id)
            .where(*filters)
        )
    ).scalar_one()
    order = resolve_sort(
        sortable_columns, sort_by, sort_dir, default=Invoice.created_at.desc()
    )
    if sort_by == "billed_for":
        # Invoices without a period (Fixed Price) go last whichever way the period sorts.
        order = order.nulls_last()
    # Every line, so that no milestone billed on a Fixed Price invoice is hidden from the
    # list; the client clips it to the column width.
    lines_summary = (
        select(
            # string_agg(description, ', ' ORDER BY position): Postgres takes the ORDER BY
            # after the last argument, the separator.
            func.string_agg(
                InvoiceLine.description,
                aggregate_order_by(literal(", "), InvoiceLine.position),
            )
        )
        .where(InvoiceLine.invoice_id == Invoice.id)
        .correlate(Invoice)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(
                Invoice,
                Project.name,
                func.coalesce(Invoice.currency_minor_unit, Currency.minor_unit),
                lines_summary,
            )
            .join(Project, Invoice.project_id == Project.id)
            .outerjoin(Currency, Invoice.currency_code == Currency.alpha_code)
            .where(*filters)
            # `Invoice.id` is a stable tie-breaker: see app/services/sorting.py.
            .order_by(order, Invoice.id)
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).all()
    return [(row[0], row[1], row[2], row[3]) for row in rows], total


# --- issuing and voiding ---------------------------------------------------------


def _project_blocks_issue(project: Project | None) -> bool:
    return project is None or not project.is_active or project.status != "active"


def _due_date(invoice: Invoice, day: date) -> date | None:
    if invoice.payment_terms is not None:
        return apply_payment_terms(invoice.payment_terms, day)
    return invoice.due_date


async def _identifiers(
    db: AsyncSession, company_id: uuid.UUID | None, day: date
) -> list[dict[str, Any]]:
    """The company's VAT, legal registration and Peppol participant identifiers valid on
    `day`, primary first, as plain values to freeze on an issued invoice."""
    if company_id is None:
        return []
    rows = (
        (
            await db.execute(
                select(PartyIdentifier)
                .where(
                    PartyIdentifier.company_id == company_id,
                    PartyIdentifier.id_type.in_(
                        ("vat", "legal_registration", "peppol_participant")
                    ),
                    (PartyIdentifier.valid_from.is_(None))
                    | (PartyIdentifier.valid_from <= day),
                    (PartyIdentifier.valid_to.is_(None))
                    | (PartyIdentifier.valid_to >= day),
                )
                .order_by(
                    PartyIdentifier.is_primary.desc(),
                    PartyIdentifier.id_type,
                    PartyIdentifier.id_value,
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id_type": row.id_type,
            "scheme_id": row.scheme_id,
            "id_value": row.id_value,
            "is_primary": row.is_primary,
        }
        for row in rows
    ]


async def issue_preview(
    db: AsyncSession, invoice: Invoice, day: date | None = None
) -> IssuePreview:
    """What issuing the draft today would give, and anything that would stop it."""
    if invoice.status != "draft":
        raise InvoiceNotDraftError()
    today = day or server_today()
    due = _due_date(invoice, today)
    fmt = await invoice_numbering_service.get_format(db)
    value = await invoice_numbering_service.peek_next(db, fmt, today)
    warnings = await invoice_warnings(db, invoice)
    if due is not None and due < today:
        warnings.append(InvoiceWarning(code="due_before_invoice_date"))
    blocking: list[BlockingReason] = []
    if _project_blocks_issue(await db.get(Project, invoice.project_id)):
        blocking.append("project_not_active")
    if not invoice.lines:
        blocking.append("no_lines")
    return IssuePreview(
        invoice_date=today,
        due_date=due,
        payment_terms=invoice.payment_terms,
        number=invoice_numbering_service.render(fmt, value, today),
        warnings=warnings,
        blocking=blocking,
    )


async def _locked(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice | None:
    """The invoice, its row locked until the transaction ends, so two requests cannot
    issue or void it at once."""
    return (
        await db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.references),
                selectinload(Invoice.taxes),
            )
            .where(Invoice.id == invoice_id)
            .with_for_update(of=Invoice)
        )
    ).scalar_one_or_none()


async def issue(
    db: AsyncSession, invoice_id: uuid.UUID, user_id: uuid.UUID, day: date | None = None
) -> Invoice | None:
    """Issues a draft in one transaction: number, dates and snapshot, or nothing at all,
    the counter included. None when the invoice does not exist."""
    invoice = await _locked(db, invoice_id)
    if invoice is None:
        return None
    if invoice.status != "draft":
        raise InvoiceNotDraftError()
    project = await db.get(Project, invoice.project_id)
    if project is None or _project_blocks_issue(project):
        raise ProjectNotActiveError()
    if not invoice.lines:
        raise NoLinesError()

    # Everything is read first and the row changed in one go afterwards: a query in
    # between would autoflush a half-issued row, which the database refuses.
    today = day or server_today()
    due_date = _due_date(invoice, today)
    _, number = await invoice_numbering_service.take_next_number(db, today)
    minor = await _minor_unit(db, invoice.currency_code)
    vendor_identifiers = await _identifiers(db, project.vendor_company_id, today)
    client_identifiers = await _identifiers(db, project.client_company_id, today)
    document_name = (await app_settings.get_group(db, "invoicing")).model_dump()[
        "document_name"
    ]

    # The amounts one last time, at the decimals now frozen with them. The tax rows are
    # updated in place: replacing them here would mean a delete and an insert mid-issue.
    for line in invoice.lines:
        line.amount = money_round(line.quantity * line.unit_price, minor)
    invoice.subtotal = sum((line.amount for line in invoice.lines), Decimal(0))
    computed = compute_taxes(
        invoice.subtotal, [_tax_input(tax) for tax in invoice.taxes], minor
    )
    for tax, result in zip(invoice.taxes, computed, strict=True):
        tax.base_mode = result.base_mode
        tax.rate = result.rate
        tax.amount = result.amount
        tax.base_amount = result.base_amount
    invoice.total = invoice.subtotal + sum(
        (result.amount for result in computed), Decimal(0)
    )
    invoice.due_date = due_date
    invoice.number = number
    invoice.invoice_date = today
    invoice.currency_minor_unit = 2 if minor is None else minor
    invoice.vendor_identifiers = vendor_identifiers
    invoice.client_identifiers = client_identifiers
    invoice.document_name = document_name
    invoice.issued_at = datetime.now(UTC)
    invoice.issued_by = user_id
    invoice.status = "issued"
    try:
        await db.flush()
    except IntegrityError as err:
        # Rolling back also returns the counter's value: nothing was issued.
        await db.rollback()
        if "uq_invoices_number" in str(err.orig):
            raise NumberAlreadyUsedError(number) from err
        raise

    # The PDF is made last, from the values just fixed, and stored in this same transaction:
    # if it cannot be made, nothing is issued and no number is used.
    stored: file_storage_service.StoredGeneratedFile | None = None
    try:
        data = build_template_data(
            invoice,
            # 0 is a real value (yen): only a missing one means 2.
            minor_unit=2
            if invoice.currency_minor_unit is None
            else invoice.currency_minor_unit,
            document_name=document_name,
            vendor_identifiers=vendor_identifiers,
            client_identifiers=client_identifiers,
            now=datetime.now(UTC),
        )
        template = await resolve_template(db)
        pdf = await render_invoice_pdf(data, template.content)
        stored = await file_storage_service.store_generated_file(
            db,
            content=pdf,
            display_name=pdf_filename(number),
            kind="invoice",
            uploaded_by=user_id,
        )
        invoice.pdf_file_id = stored.file.id
        await db.commit()
    except PdfError as err:
        await db.rollback()
        logger.exception("Could not make the PDF of invoice %s", number)
        raise PdfUnavailableError() from err
    except BaseException:
        await db.rollback()
        if stored is not None:
            await file_storage_service.discard_generated_file(stored)
        raise
    return invoice


async def void(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    reason: str | None,
    user_id: uuid.UUID,
) -> Invoice | None:
    """Cancels an issued invoice. It keeps its number and stays in the list as evidence that
    it existed; nothing else changes. None when the invoice does not exist."""
    invoice = await _locked(db, invoice_id)
    if invoice is None:
        return None
    if invoice.status != "issued":
        raise InvoiceNotIssuedError()

    # The PDF that was sent is marked, not made again: read it and stamp it before anything
    # changes, so a PDF that cannot be marked leaves the invoice issued. An invoice issued
    # before PDFs were kept has none and is simply voided.
    stamped: bytes | None = None
    # Read before any rollback, which expires the row's attributes.
    number = invoice.number
    if invoice.pdf_file_id is not None:
        try:
            original = await stored_pdf(db, invoice)
        except (OSError, file_storage_service.StoragePathError) as err:
            await db.rollback()
            raise PdfStampError("The issued PDF cannot be read") from err
        if original is None:
            await db.rollback()
            raise PdfStampError("The issued PDF is missing")
        try:
            stamped = await asyncio.to_thread(stamp_voided, original)
        except PdfStampError:
            await db.rollback()
            logger.exception("Could not mark the PDF of invoice %s as void", number)
            raise

    invoice.status = "void"
    invoice.voided_at = datetime.now(UTC)
    invoice.voided_by = user_id
    invoice.void_reason = reason or None
    stored: file_storage_service.StoredGeneratedFile | None = None
    try:
        if stamped is not None:
            # A second file: the issued original stays in storage, no longer referenced.
            stored = await file_storage_service.store_generated_file(
                db,
                content=stamped,
                display_name=pdf_filename(number or "invoice"),
                kind="invoice",
                uploaded_by=user_id,
            )
            invoice.pdf_file_id = stored.file.id
        await db.commit()
    except BaseException:
        await db.rollback()
        if stored is not None:
            await file_storage_service.discard_generated_file(stored)
        raise
    return invoice
