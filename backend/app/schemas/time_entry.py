import uuid
from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, model_validator


class TimeEntryUpsert(BaseModel):
    service_line_id: uuid.UUID
    date: date_
    hours: Decimal

    @model_validator(mode="after")
    def check_hours(self) -> "TimeEntryUpsert":
        if self.hours < 0 or self.hours > 24:
            raise ValueError("hours must be between 0 and 24")
        if (self.hours * 2) % 1 != 0:
            raise ValueError("hours must be in 0.5 increments")
        return self


class TimeEntryOut(BaseModel):
    id: uuid.UUID
    service_line_id: uuid.UUID
    service_line_name: str | None
    project_id: uuid.UUID
    project_name: str
    date: date_
    hours: Decimal
    is_locked: bool


class TimeEntryListResponse(BaseModel):
    items: list[TimeEntryOut]


class TimeEntryUpsertResult(BaseModel):
    """One request item's outcome from the bulk `PUT /time-entries` (see
    docs/requirements/timesheet.md's "API contract" — every item in the request
    array is processed and reported independently, never all-or-nothing).
    `entry`/`error` are mutually exclusive: `entry` is set (or left `None` for a
    successful delete) when `ok` is `True`; `error` is set — `"locked"` or
    `"not_eligible"` — when `ok` is `False`."""

    service_line_id: uuid.UUID
    date: date_
    ok: bool
    entry: TimeEntryOut | None = None
    error: str | None = None


class EligibleServiceLineOut(BaseModel):
    service_line_id: uuid.UUID
    service_line_name: str | None
    project_id: uuid.UUID
    project_name: str


class EligibleServiceLineListResponse(BaseModel):
    items: list[EligibleServiceLineOut]
