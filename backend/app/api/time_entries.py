from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.time_entry import (
    EligibleServiceLineListResponse,
    ManagedTimeEntriesResponse,
    TimeEntryListResponse,
    TimeEntryLockRequest,
    TimeEntryOut,
    TimeEntryUpsert,
    TimeEntryUpsertResult,
)
from app.services import time_entry_service
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


@router.get("/managed", response_model=ManagedTimeEntriesResponse)
async def list_managed_time_entries(
    start_date: date,
    end_date: date,
    user: User = Depends(require_roles("project_manager")),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> ManagedTimeEntriesResponse:
    """Validation screen's one-call-loads-everything endpoint — no identity
    parameter, the caller's own project_manager assignments determine the whole
    response. `GET /time-entries` and `GET /time-entries/eligible-service-lines`
    are unrelated and unchanged; this is a separate, purpose-built read path."""
    consultants = await time_entry_service.list_managed_time_entries(
        db, user, start_date, end_date
    )
    return ManagedTimeEntriesResponse(consultants=consultants)


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
