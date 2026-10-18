import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.schemas.invoice import (
    BillingContext,
    GenerateRequest,
    GenerateResponse,
    InvoiceableProject,
    InvoiceDetail,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceWrite,
    IssuePreview,
    VoidWrite,
)
from app.services import invoice_service
from app.services.invoice_service import (
    InvalidInvoiceDataError,
    InvoiceNotDraftError,
    InvoiceNotIssuedError,
    NoLinesError,
    NumberAlreadyUsedError,
    ProjectNotActiveError,
    ProjectNotInvoiceableError,
)

_billing = Depends(require_roles("billing"))

router = APIRouter(prefix="/invoices", tags=["invoices"], dependencies=[_billing])

_NOT_INVOICEABLE = "A new invoice can only be started for an Active Time & Material or Capped T&M project"
_NOT_DRAFT = "Only a draft invoice can be changed or deleted"
# The same sentence the form's banner shows.
_PROJECT_NOT_ACTIVE = "This invoice cannot be issued because its project is not Active."


async def _get_invoice_or_404(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    invoice = await invoice_service.get_invoice(db, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return invoice


# Declared before `/{invoice_id}`: routes match in declaration order, and a plain
# `{invoice_id}` segment would otherwise take `projects` and `generate` and reject them as
# invalid UUIDs.


@router.get("/projects", response_model=list[InvoiceableProject])
async def list_projects(
    search: str | None = None,
    invoiced: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceableProject]:
    """Without `invoiced`, the projects a new invoice can be started for; with it, every
    project that has invoices, for the list's filter."""
    return await invoice_service.list_projects(db, search, invoiced)


@router.get("/projects/{project_id}", response_model=BillingContext)
async def get_billing_context(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BillingContext:
    context = await invoice_service.billing_context(db, project_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return context


@router.post("/generate", response_model=GenerateResponse)
async def generate_lines(
    payload: GenerateRequest, db: AsyncSession = Depends(get_db)
) -> GenerateResponse:
    try:
        return await invoice_service.generate_lines(db, payload)
    except InvalidInvoiceDataError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(default=1, ge=1),
    sort_by: str | None = None,
    sort_dir: str | None = None,
    project_id: uuid.UUID | None = None,
    # Repeated (?status=draft&status=void). Left out, the list is drafts and issued
    # invoices: void ones are hidden unless asked for.
    status_filter: list[InvoiceStatus] | None = Query(default=None, alias="status"),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> InvoiceListResponse:
    rows, total = await invoice_service.list_invoices(
        db,
        page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        project_id=project_id,
        statuses=status_filter,
        search=search,
    )
    return InvoiceListResponse(
        items=[
            InvoiceListItem(
                id=invoice.id,
                status=invoice.status,
                project_id=invoice.project_id,
                project_name=project_name,
                client_name=invoice.bill_to_name,
                period_start=invoice.period_start,
                period_end=invoice.period_end,
                currency_code=invoice.currency_code,
                currency_minor_unit=minor_unit,
                total=invoice.total,
                payment_terms=invoice.payment_terms,
                due_date=invoice.due_date,
                created_at=invoice.created_at,
                number=invoice.number,
                invoice_date=invoice.invoice_date,
                issued_at=invoice.issued_at,
                lines_summary=lines_summary,
            )
            for invoice, project_name, minor_unit, lines_summary in rows
        ],
        total=total,
        page=page,
        page_size=invoice_service.PAGE_SIZE,
    )


@router.post("", response_model=InvoiceDetail, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceWrite,
    user: User = _billing,
    db: AsyncSession = Depends(get_db),
) -> InvoiceDetail:
    try:
        invoice = await invoice_service.create_invoice(db, payload, user.id)
    except ProjectNotInvoiceableError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_NOT_INVOICEABLE
        ) from err
    except InvalidInvoiceDataError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    return await invoice_service.to_detail(
        db, await _get_invoice_or_404(db, invoice.id)
    )


@router.get("/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> InvoiceDetail:
    return await invoice_service.to_detail(
        db, await _get_invoice_or_404(db, invoice_id)
    )


@router.patch("/{invoice_id}", response_model=InvoiceDetail)
async def update_invoice(
    invoice_id: uuid.UUID, payload: InvoiceWrite, db: AsyncSession = Depends(get_db)
) -> InvoiceDetail:
    invoice = await _get_invoice_or_404(db, invoice_id)
    try:
        await invoice_service.update_invoice(db, invoice, payload)
    except InvoiceNotDraftError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_NOT_DRAFT
        ) from err
    except ProjectNotInvoiceableError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_NOT_INVOICEABLE
        ) from err
    except InvalidInvoiceDataError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    return await invoice_service.to_detail(
        db, await _get_invoice_or_404(db, invoice_id)
    )


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    invoice = await _get_invoice_or_404(db, invoice_id)
    try:
        await invoice_service.delete_invoice(db, invoice)
    except InvoiceNotDraftError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_NOT_DRAFT
        ) from err


@router.post(
    "/{invoice_id}/duplicate",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_invoice(
    invoice_id: uuid.UUID,
    user: User = _billing,
    db: AsyncSession = Depends(get_db),
) -> InvoiceDetail:
    invoice = await _get_invoice_or_404(db, invoice_id)
    try:
        copy = await invoice_service.duplicate_invoice(db, invoice, user.id)
    except ProjectNotInvoiceableError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_NOT_INVOICEABLE
        ) from err
    return await invoice_service.to_detail(db, await _get_invoice_or_404(db, copy.id))


@router.get("/{invoice_id}/issue-preview", response_model=IssuePreview)
async def get_issue_preview(
    invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> IssuePreview:
    invoice = await _get_invoice_or_404(db, invoice_id)
    try:
        return await invoice_service.issue_preview(db, invoice)
    except InvoiceNotDraftError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft invoice can be issued",
        ) from err


@router.post("/{invoice_id}/issue", response_model=InvoiceDetail)
async def issue_invoice(
    invoice_id: uuid.UUID,
    user: User = _billing,
    db: AsyncSession = Depends(get_db),
) -> InvoiceDetail:
    try:
        issued = await invoice_service.issue(db, invoice_id, user.id)
    except InvoiceNotDraftError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft invoice can be issued",
        ) from err
    except ProjectNotActiveError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_PROJECT_NOT_ACTIVE
        ) from err
    except NoLinesError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invoice needs at least one line",
        ) from err
    except NumberAlreadyUsedError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"The number {err.number} is already used. An administrator must set the "
                "next number in Configuration → Invoices."
            ),
        ) from err
    if issued is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return await invoice_service.to_detail(
        db, await _get_invoice_or_404(db, invoice_id)
    )


@router.post("/{invoice_id}/void", response_model=InvoiceDetail)
async def void_invoice(
    invoice_id: uuid.UUID,
    payload: VoidWrite,
    user: User = _billing,
    db: AsyncSession = Depends(get_db),
) -> InvoiceDetail:
    try:
        voided = await invoice_service.void(db, invoice_id, payload.reason, user.id)
    except InvoiceNotIssuedError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an issued invoice can be voided",
        ) from err
    if voided is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return await invoice_service.to_detail(
        db, await _get_invoice_or_404(db, invoice_id)
    )
