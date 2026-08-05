import { apiClient } from "@/api/client";
import type {
  EligibleServiceLineListResponse,
  TimeEntry,
  TimeEntryListResponse,
  TimeEntryUpsertInput,
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

export function upsertTimeEntry(payload: TimeEntryUpsertInput) {
  return apiClient.put<TimeEntry | null>("/time-entries", payload);
}
