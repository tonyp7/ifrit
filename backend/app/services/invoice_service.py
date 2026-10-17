import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company, PayeeAccount
from app.models.currency import Currency
from app.models.invoice import Invoice, InvoiceLine, InvoiceReference
from app.models.project import Project, ProjectType, ServiceLine
from app.models.time_entry import TimeEntry
from app.schemas.company import BankAddress
from app.schemas.invoice import (
    BillingContext,
    ContextAddress,
    ContextCompany,
    ContextPayeeAccount,
    ContextServiceLine,
    GeneratedLine,
    GenerateRequest,
    GenerateResponse,
    InvoiceableProject,
    InvoiceDetail,
    InvoiceLineOut,
    InvoiceLineWrite,
    InvoicePayeeOut,
    InvoicePayeeWrite,
    InvoiceReferenceOut,
    InvoiceWarning,
    InvoiceWrite,
    OmittedServiceLine,
    PartyOut,
    PartyWrite,
    UnlockedServiceLine,
)
from app.schemas.project import ProjectReferenceWrite
from app.services import app_settings
from app.services.sorting import resolve_sort

PAGE_SIZE = 50
# Fixed Price projects are billed from milestones, which this version cannot invoice yet.
INVOICEABLE_TYPES: tuple[ProjectType, ...] = ("time_and_material", "capped_tm")
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


class ProjectNotInvoiceableError(Exception):
    """The project cannot have a new invoice: deleted, not Active, or not Time & Material."""


class InvoiceNotDraftError(Exception):
    pass


class InvalidInvoiceDataError(Exception):
    """A value refers to something that does not fit: a service line of another project,
    an unknown currency."""


def money_round(value: Decimal, minor_unit: int | None) -> Decimal:
    """Rounds to the currency's minor unit (2 when it has none defined), half away from
    zero, the usual commercial rule. ROUND_HALF_UP on Decimal rounds away from zero for
    negative amounts too, so a discount rounds like the charge it offsets."""
    places = 2 if minor_unit is None else minor_unit
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


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


async def generate_tm_lines(
    db: AsyncSession, data: GenerateRequest
) -> GenerateResponse:
    """Previews the lines for the selected service lines and period. Saves nothing and
    never locks or unlocks an entry: locking belongs to the timesheet."""
    project = await db.get(Project, data.project_id)
    if project is None or not project.is_active:
        raise InvalidInvoiceDataError("Project not found")
    if project.project_type not in INVOICEABLE_TYPES:
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
    """Writes every draft field from `data`, replaces the lines and references, and
    recomputes the stored amounts. The currency always follows the project."""
    await _check_payee_currency(db, data.payee)
    invoice.project_id = project.id
    invoice.currency_code = project.invoicing_currency
    _set_party(invoice, "bill_from", data.bill_from)
    _set_party(invoice, "bill_to", data.bill_to)
    invoice.period_start = data.period_start
    invoice.period_end = data.period_end
    invoice.payment_terms = data.payment_terms
    invoice.due_date = data.due_date
    _set_payee(invoice, data.payee)

    minor = await _minor_unit(db, project.invoicing_currency)
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
    invoice.total = invoice.subtotal


async def create_invoice(
    db: AsyncSession, data: InvoiceWrite, user_id: uuid.UUID
) -> Invoice:
    project = await db.get(Project, data.project_id)
    if project is None or not is_invoiceable(project):
        raise ProjectNotInvoiceableError()
    invoice = Invoice(status="draft", created_by=user_id, lines=[], references=[])
    await _apply(db, invoice, data, project)
    db.add(invoice)
    await db.commit()
    return invoice


async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice | None:
    return (
        await db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.references),
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
    )


async def duplicate_invoice(
    db: AsyncSession, invoice: Invoice, user_id: uuid.UUID
) -> Invoice:
    """A new draft with the source's content. Created even when the project can no longer
    take a new invoice: the copy is a starting point, and issuing it is what is refused."""
    project = await db.get(Project, invoice.project_id)
    if project is None:
        raise ProjectNotInvoiceableError()
    copy = Invoice(status="draft", created_by=user_id, lines=[], references=[])
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
    if invoice.payee_payment_means_code is None:
        warnings.append(InvoiceWarning(code="no_payee_account"))
    elif invoice.payee_currency_code != invoice.currency_code:
        warnings.append(InvoiceWarning(code="payee_currency"))
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
        currency_minor_unit=await _minor_unit(db, invoice.currency_code),
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
        total=invoice.total,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        warnings=await invoice_warnings(db, invoice),
    )


async def list_invoices(
    db: AsyncSession,
    page: int,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    project_id: uuid.UUID | None = None,
) -> tuple[list[tuple[Invoice, str, int | None]], int]:
    """(invoice, project name, currency minor unit) rows, newest first by default."""
    sortable_columns = {
        "created_at": Invoice.created_at,
        "project": Project.name,
        "client": Invoice.bill_to_name,
        "billed_for": Invoice.period_start,
        "status": Invoice.status,
        "total": Invoice.total,
        "due": Invoice.due_date,
    }
    filters: list[ColumnElement[bool]] = []
    if project_id is not None:
        filters.append(Invoice.project_id == project_id)
    total = (
        await db.execute(select(func.count()).select_from(Invoice).where(*filters))
    ).scalar_one()
    order = resolve_sort(
        sortable_columns, sort_by, sort_dir, default=Invoice.created_at.desc()
    )
    rows = (
        await db.execute(
            select(Invoice, Project.name, Currency.minor_unit)
            .join(Project, Invoice.project_id == Project.id)
            .outerjoin(Currency, Invoice.currency_code == Currency.alpha_code)
            .where(*filters)
            # `Invoice.id` is a stable tie-breaker: see app/services/sorting.py.
            .order_by(order, Invoice.id)
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).all()
    return [(row[0], row[1], row[2]) for row in rows], total
