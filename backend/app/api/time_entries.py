from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.time_entry import (
    EligibleServiceLineListResponse,
    TimeEntryListResponse,
    TimeEntryOut,
    TimeEntryUpsert,
)
from app.services import time_entry_service
from app.services.time_entry_service import NotEligibleError

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


@router.put("", response_model=TimeEntryOut | None)
async def upsert_time_entry(
    payload: TimeEntryUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TimeEntryOut | None:
    try:
        result = await time_entry_service.upsert_time_entry(db, user, payload)
    except NotEligibleError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    if result is None:
        return None
    entry, line, project = result
    return time_entry_service.to_time_entry_out(entry, line, project)
