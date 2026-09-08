import { apiClient } from "@/api/client";
import type {
  EligibleServiceLineListResponse,
  ManagedTimeEntriesResponse,
  ServiceLineLockRequest,
  TimeEntry,
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

// Always an array, request and response — a single cell blur sends a one-element
// array (see handleCellBlur in TimesheetPage.tsx). apiClient's fetch
// wrapper treats a 207 (partial success) as a normal, parsed response — same as a
// 200 — since 207 is in fetch's `response.ok` range (200-299); callers must inspect
// each result's own `ok` field, not rely on the HTTP status to distinguish outcomes.
export function upsertTimeEntries(payload: TimeEntryUpsertInput[]) {
  return apiClient.put<TimeEntryUpsertResult[]>("/time-entries", payload);
}

// Validation screen's one-call-loads-everything read.
export function getManagedTimeEntries(startDate: string, endDate: string) {
  const query = new URLSearchParams({ start_date: startDate, end_date: endDate });
  return apiClient.get<ManagedTimeEntriesResponse>(
    `/time-entries/managed?${query.toString()}`,
  );
}

// Lock/unlock a whole (consultant, service line, period) at once.
export function setServiceLineLock(payload: ServiceLineLockRequest) {
  return apiClient.put<TimeEntry[]>("/time-entries/lock", payload);
}
