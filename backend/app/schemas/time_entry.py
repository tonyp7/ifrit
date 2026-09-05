import uuid
from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, model_validator


class TimeEntryUpsert(BaseModel):
    service_line_id: uuid.UUID
    date: date_
    hours: Decimal
    # None (the default, and the only value My Timesheet's own calls ever send) means
    # "the caller's own entry" — see docs/requirements/timesheet.md's Validation
    # § Scope "Editing (override)": a project_manager overriding a consultant's entry
    # sets this to that consultant's id. Never resolved from anywhere but this field —
    # see time_entry_service._upsert_one's authorization check.
    user_id: uuid.UUID | None = None

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
    successful delete) when `ok` is `True`; `error` is set — `"locked"`,
    `"not_eligible"`, or `"not_authorized"` (a `project_manager` override rejected
    for lacking assignment to the target service line's project, or a non-
    `project_manager` attempting an override at all) — when `ok` is `False`."""

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


class ManagedConsultantOut(BaseModel):
    """One consultant's block on the Validation screen — see
    docs/requirements/timesheet.md's "GET /time-entries/managed" API contract."""

    user_id: uuid.UUID
    full_name: str
    entries: list[TimeEntryOut]
    # Deliberately the same *unfiltered* eligibility shape as
    # GET /time-entries/eligible-service-lines, not pre-filtered to "addable" —
    # the frontend derives both the Add-dropdown options and each shown row's
    # "still currently assigned" editability from this same set, mirroring how
    # My Timesheet's own eligibleLines/addOptions split already works.
    eligible_service_lines: list[EligibleServiceLineOut]


class ManagedTimeEntriesResponse(BaseModel):
    consultants: list[ManagedConsultantOut]


class TimeEntryLockRequest(BaseModel):
    """PUT /time-entries/lock — see docs/requirements/timesheet.md's Validation §
    Lock / Unlock. One (consultant, service line, period) action per call, not a
    bulk array — there's no equivalent "many independent items" shape here."""

    user_id: uuid.UUID
    service_line_id: uuid.UUID
    start_date: date_
    end_date: date_
    locked: bool
