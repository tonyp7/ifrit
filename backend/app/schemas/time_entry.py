import uuid
from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, model_validator


class TimeEntryUpsert(BaseModel):
    service_line_id: uuid.UUID
    date: date_
    hours: Decimal
    # None (the default, and the only value My Timesheet's own calls ever send) means
    # "the caller's own entry"; a project_manager overriding a consultant's entry sets
    # this to that consultant's id instead. Never resolved from anywhere but this field —
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
    """One request item's outcome from the bulk `PUT /time-entries` — every item in the
    request array is processed and reported independently, never all-or-nothing.
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


class TimeEntryLockRequest(BaseModel):
    """PUT /time-entries/lock. One (consultant, service line, period) action per call,
    not a bulk array — unlike the entry-upsert endpoint above, there's no batch of
    independent lock actions to report on individually."""

    user_id: uuid.UUID
    service_line_id: uuid.UUID
    start_date: date_
    end_date: date_
    locked: bool


class ReportFilterProjectOut(BaseModel):
    project_id: uuid.UUID
    name: str
    status: str


class ReportFilterServiceLineOut(BaseModel):
    service_line_id: uuid.UUID
    service_line_name: str | None
    project_id: uuid.UUID
    project_name: str


class ReportFilterConsultantOut(BaseModel):
    user_id: uuid.UUID
    full_name: str


class TimesheetReportFiltersOut(BaseModel):
    """GET /time-entries/report/filters. Populates the Reporting screen's four
    filter dropdowns — static, not period-scoped, and deliberately not restricted
    to active projects/service lines the way GET /time-entries/eligible-service-lines
    is, since Reporting needs closed-project/inactive-line history reachable too."""

    projects: list[ReportFilterProjectOut]
    service_lines: list[ReportFilterServiceLineOut]
    consultants: list[ReportFilterConsultantOut]


class TimesheetReportRowOut(BaseModel):
    """One row of GET /time-entries/report — a (consultant, service_line) pair, not
    grouped by consultant. `is_assigned` is
    deliberately the *narrower* existing eligibility rule (active project + active
    service line + current assignment) — the same one PUT /time-entries' per-item
    handler already enforces before accepting an hours > 0 write — reused here so
    the UI's Unassigned/read-only cell state always matches what an edit would
    actually be accepted, even on a row that's visible because it's historical or a
    since-closed-project assignment."""

    user_id: uuid.UUID
    full_name: str
    project_id: uuid.UUID
    project_name: str
    project_status: str
    service_line_id: uuid.UUID
    service_line_name: str | None
    entries: list[TimeEntryOut]
    is_assigned: bool


class TimesheetReportResponse(BaseModel):
    items: list[TimesheetReportRowOut]
