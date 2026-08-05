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
