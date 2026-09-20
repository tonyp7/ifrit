import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.time_entry import (
    EligibleServiceLineListResponse,
    TimeEntryListResponse,
    TimeEntryLockRequest,
    TimeEntryOut,
    TimeEntryUpsert,
    TimeEntryUpsertResult,
    TimesheetReportFiltersOut,
    TimesheetReportResponse,
)
from app.services import report_export_service, time_entry_service
from app.services.time_entry_service import NotAuthorizedError

router = APIRouter(
    prefix="/time-entries",
    tags=["time-entries"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=TimeEntryListResponse)
async def list_time_entries(
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TimeEntryListResponse:
    rows = await time_entry_service.list_time_entries(db, user.id, start_date, end_date)
    return TimeEntryListResponse(
        items=[
            time_entry_service.to_time_entry_out(entry, line, project)
            for entry, line, project in rows
        ]
    )


@router.get("/eligible-service-lines", response_model=EligibleServiceLineListResponse)
async def list_eligible_service_lines(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EligibleServiceLineListResponse:
    rows = await time_entry_service.list_eligible_service_lines(db, user.id)
    return EligibleServiceLineListResponse(
        items=[
            time_entry_service.to_eligible_service_line_out(line, project)
            for line, project in rows
        ]
    )


@router.put("", response_model=list[TimeEntryUpsertResult])
async def upsert_time_entries(
    payload: list[TimeEntryUpsert],
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TimeEntryUpsertResult]:
    """Bulk, per-item-validated — a single cell blur sends a one-element `payload`,
    the timesheet's clear-on-remove-service-line flow sends one covering every day
    being cleared.
    `200` only if every item succeeded; `207 Multi-Status` if any item was rejected
    (locked, or not currently assigned to the service line) — whether that's one item
    or all of them, the response array already carries the per-item detail a caller
    needs, so there's no separate all-rejected status."""
    results = await time_entry_service.upsert_time_entries(db, user, payload)
    if any(not result.ok for result in results):
        response.status_code = status.HTTP_207_MULTI_STATUS
    return results


@router.get("/report/filters", response_model=TimesheetReportFiltersOut)
async def get_report_filters(
    user: User = Depends(require_roles("project_manager")),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> TimesheetReportFiltersOut:
    """Reporting screen's filter dropdowns — static, not period-scoped, one fetch
    on mount. Covers every project status (unlike /eligible-service-lines), since
    Reporting needs closed-project/inactive-line history reachable too."""
    return await time_entry_service.list_report_filters(db, user)


@router.get("/report", response_model=TimesheetReportResponse)
async def get_time_entries_report(
    start_date: date,
    end_date: date,
    project_ids: list[uuid.UUID] | None = Query(default=None),
    service_line_ids: list[uuid.UUID] | None = Query(default=None),
    consultant_ids: list[uuid.UUID] | None = Query(default=None),
    statuses: list[str] | None = Query(default=None),
    user: User = Depends(require_roles("project_manager")),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> TimesheetReportResponse:
    """Reporting screen's row data — a flat, pre-sorted (consultant, service_line)
    list, not grouped by consultant. All four filter params are
    optional; omitted means no restriction on that dimension. Any id outside the
    caller's own project_manager scope is silently dropped, never a 403."""
    rows = await time_entry_service.list_time_entries_report(
        db,
        user,
        start_date,
        end_date,
        project_ids,
        service_line_ids,
        consultant_ids,
        statuses,
    )
    return TimesheetReportResponse(items=rows)


@router.get("/report/export")
async def export_time_entries_report(
    format: Literal["pdf", "xlsx", "csv"],
    period_type: Literal["week", "month"],
    start_date: date,
    end_date: date,
    project_ids: list[uuid.UUID] | None = Query(default=None),
    service_line_ids: list[uuid.UUID] | None = Query(default=None),
    consultant_ids: list[uuid.UUID] | None = Query(default=None),
    statuses: list[str] | None = Query(default=None),
    user: User = Depends(require_roles("project_manager")),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Reporting screen's export — deliberately the exact same filter params as
    GET /time-entries/report (plus format/period_type, which that endpoint has no
    use for), so an export always matches whatever the screen is currently
    showing. Always re-queries fresh server-side; never a client-supplied payload
    of already-rendered rows, so an unblurred, not-yet-saved cell edit can never
    appear in an export."""
    file_bytes, filename, content_type = await report_export_service.build_report_export(
        db,
        user,
        export_format=format,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
        project_ids=project_ids,
        service_line_ids=service_line_ids,
        consultant_ids=consultant_ids,
        statuses=statuses,
    )

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # Same forced-download hardening fileupload.md already establishes
            # for every other download in this app.
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/lock", response_model=list[TimeEntryOut])
async def set_service_line_lock(
    payload: TimeEntryLockRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TimeEntryOut]:
    """Lock/unlock a whole (consultant, service line, period) at once. A single
    action, not a bulk array like PUT /time-entries: any failing authorization
    check rejects the whole request rather than partially applying."""
    try:
        return await time_entry_service.set_service_line_lock(db, user, payload)
    except NotAuthorizedError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(err)
        ) from err
