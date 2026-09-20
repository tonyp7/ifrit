export type PeriodType = "week" | "month";

export interface TimeEntry {
  id: string;
  service_line_id: string;
  service_line_name: string | null;
  project_id: string;
  project_name: string;
  date: string;
  hours: string;
  is_locked: boolean;
}

export interface TimeEntryListResponse {
  items: TimeEntry[];
}

export interface EligibleServiceLine {
  service_line_id: string;
  service_line_name: string | null;
  project_id: string;
  project_name: string;
}

export interface EligibleServiceLineListResponse {
  items: EligibleServiceLine[];
}

export interface TimeEntryUpsertInput {
  service_line_id: string;
  date: string;
  hours: string;
  // Omitted (or undefined) means "the caller's own entry". Only ever set by the
  // Reporting screen, when a project_manager overrides a consultant's entry, to
  // that consultant's id.
  user_id?: string;
}

// One request item's outcome from the bulk `PUT /time-entries` — the
// request/response are always arrays, even for a single cell edit.
// `entry`/`error` are mutually exclusive:
// `entry` is set (or `null` for a successful delete) when `ok` is `true`; `error` —
// `"locked"`, `"not_eligible"`, or `"not_authorized"` (a rejected project_manager
// override) — is set when `ok` is `false`.
export interface TimeEntryUpsertResult {
  service_line_id: string;
  date: string;
  ok: boolean;
  entry: TimeEntry | null;
  error: "locked" | "not_eligible" | "not_authorized" | null;
}

// Client-side row shown in `serviceLines` state — a subset of the fields
// TimeEntry/EligibleServiceLine both already carry, common to whichever one a
// row came from. `user_id` is always the row's owner (the caller's own id on My
// Timesheet, a consultant's id on Reporting) — it's what cellKey uses
// to key local state, not just an API-payload concern. `consultant_name` is
// Reporting-only: when set, TimesheetDesktopGrid/TimesheetMobileView render it as
// a third line in the row label, since a Reporting row can belong to any
// consultant, not just one implicit owner.
export interface ServiceLineRow {
  service_line_id: string;
  service_line_name: string | null;
  project_id: string;
  project_name: string;
  user_id: string;
  consultant_name?: string;
}

// A single cell's local, editable state — `hours` is the live-typed or
// last-saved value, never re-parsed until blur.
export interface EntryCell {
  hours: string;
  is_locked: boolean;
}

// PUT /time-entries/lock. One (consultant, service line, period) action per
// call, not a bulk array.
export interface ServiceLineLockRequest {
  user_id: string;
  service_line_id: string;
  start_date: string;
  end_date: string;
  locked: boolean;
}

// Reporting screen's four filter dropdowns — GET /time-entries/report/filters.
// Static, not period-scoped: fetched once on mount, not re-fetched on period or
// filter changes.
export interface ReportFilterProject {
  project_id: string;
  name: string;
  status: "draft" | "active" | "closed";
}

export interface ReportFilterServiceLine {
  service_line_id: string;
  service_line_name: string | null;
  project_id: string;
  project_name: string;
}

export interface ReportFilterConsultant {
  user_id: string;
  full_name: string;
}

export interface TimesheetReportFilters {
  projects: ReportFilterProject[];
  service_lines: ReportFilterServiceLine[];
  consultants: ReportFilterConsultant[];
}

// One row of GET /time-entries/report — a (consultant, service_line) pair, not
// grouped by consultant. `is_assigned` is deliberately the *narrower* eligibility
// rule (see the backend's own docstring on TimesheetReportRowOut) — it's what
// isUnassignedInPeriod is derived from on this screen, since Reporting has no
// `eligible_service_lines` list to check a row against the way My Timesheet does.
export interface TimesheetReportRow {
  user_id: string;
  full_name: string;
  project_id: string;
  project_name: string;
  project_status: "draft" | "active" | "closed";
  service_line_id: string;
  service_line_name: string | null;
  entries: TimeEntry[];
  is_assigned: boolean;
}

export interface TimesheetReportResponse {
  items: TimesheetReportRow[];
}
