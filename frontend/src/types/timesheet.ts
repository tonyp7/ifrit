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
  // Omitted (or undefined) means "the caller's own entry" — see
  // specs/requirements/timesheet.md's Validation § Scope "Editing (override)". Only
  // ever set by the Validation screen, when a project_manager overrides a
  // consultant's entry, to that consultant's id.
  user_id?: string;
}

// One request item's outcome from the bulk `PUT /time-entries` (see
// specs/requirements/timesheet.md's "API contract" — the request/response are always
// arrays, even for a single cell edit). `entry`/`error` are mutually exclusive:
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

// Client-side row shown in `serviceLines` state (see
// specs/requirements/timesheet.md#state) — a subset of the fields TimeEntry/
// EligibleServiceLine both already carry, common to whichever one a row came from.
export interface ServiceLineRow {
  service_line_id: string;
  service_line_name: string | null;
  project_id: string;
  project_name: string;
}

// A single cell's local, editable state (see
// specs/requirements/timesheet.md#persistence) — `hours` is the live-typed or
// last-saved value, never re-parsed until blur.
export interface EntryCell {
  hours: string;
  is_locked: boolean;
}

// One consultant's block on the Validation screen — see
// specs/requirements/timesheet.md's "GET /time-entries/managed" API contract.
export interface ManagedConsultant {
  user_id: string;
  full_name: string;
  entries: TimeEntry[];
  // Deliberately unfiltered — see ManagedConsultantOut on the backend. The
  // frontend derives both the Add-dropdown options and each row's "still
  // currently assigned" editability from this same set.
  eligible_service_lines: EligibleServiceLine[];
}

export interface ManagedTimeEntriesResponse {
  consultants: ManagedConsultant[];
}

// PUT /time-entries/lock — see specs/requirements/timesheet.md's Validation §
// Lock / Unlock. One (consultant, service line, period) action per call, not a
// bulk array.
export interface ServiceLineLockRequest {
  user_id: string;
  service_line_id: string;
  start_date: string;
  end_date: string;
  locked: boolean;
}
