import { apiClient } from "@/api/client";
import type {
  EligibleServiceLineListResponse,
  TimeEntryListResponse,
  TimeEntryUpsertInput,
  TimeEntryUpsertResult,
} from "@/types/timesheet";

export function listTimeEntries(startDate: string, endDate: string) {
  const query = new URLSearchParams({ start_date: startDate, end_date: endDate });
  return apiClient.get<TimeEntryListResponse>(`/time-entries?${query.toString()}`);
}

export function listEligibleServiceLines() {
  return apiClient.get<EligibleServiceLineListResponse>(
    "/time-entries/eligible-service-lines",
  );
}

// Always an array, request and response — see
// docs/requirements/timesheet.md's "API contract" — a single cell blur sends a
// one-element array (see handleCellBlur in TimesheetPage.tsx). apiClient's fetch
// wrapper treats a 207 (partial success) as a normal, parsed response — same as a
// 200 — since 207 is in fetch's `response.ok` range (200-299); callers must inspect
// each result's own `ok` field, not rely on the HTTP status to distinguish outcomes.
export function upsertTimeEntries(payload: TimeEntryUpsertInput[]) {
  return apiClient.put<TimeEntryUpsertResult[]>("/time-entries", payload);
}
