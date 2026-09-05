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
}

// One request item's outcome from the bulk `PUT /time-entries` (see
// docs/requirements/timesheet.md's "API contract" — the request/response are always
// arrays, even for a single cell edit). `entry`/`error` are mutually exclusive:
// `entry` is set (or `null` for a successful delete) when `ok` is `true`; `error` —
// `"locked"` or `"not_eligible"` — is set when `ok` is `false`.
export interface TimeEntryUpsertResult {
  service_line_id: string;
  date: string;
  ok: boolean;
  entry: TimeEntry | null;
  error: "locked" | "not_eligible" | null;
}

// Client-side row shown in `serviceLines` state (see
// docs/requirements/timesheet.md#state) — a subset of the fields TimeEntry/
// EligibleServiceLine both already carry, common to whichever one a row came from.
export interface ServiceLineRow {
  service_line_id: string;
  service_line_name: string | null;
  project_id: string;
  project_name: string;
}

// A single cell's local, editable state (see
// docs/requirements/timesheet.md#persistence) — `hours` is the live-typed or
// last-saved value, never re-parsed until blur.
export interface EntryCell {
  hours: string;
  is_locked: boolean;
}
