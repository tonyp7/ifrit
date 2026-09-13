import { apiClient } from "@/api/client";
import type {
  EligibleServiceLineListResponse,
  ManagedTimeEntriesResponse,
  ServiceLineLockRequest,
  TimeEntry,
  TimeEntryListResponse,
  TimeEntryUpsertInput,
  TimeEntryUpsertResult,
  TimesheetReportFilters,
  TimesheetReportResponse,
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

// Reporting screen's filter dropdowns — static, not period-scoped, one fetch on
// mount.
export function getReportFilters() {
  return apiClient.get<TimesheetReportFilters>("/time-entries/report/filters");
}

export interface TimesheetReportParams {
  startDate: string;
  endDate: string;
  projectIds?: string[];
  serviceLineIds?: string[];
  consultantIds?: string[];
  statuses?: string[];
}

// Reporting screen's row data — a flat, pre-sorted (consultant, service_line)
// list. All four filter arrays are optional; omitted/empty means no restriction
// on that dimension.
export function getTimesheetReport(params: TimesheetReportParams) {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  for (const id of params.projectIds ?? []) query.append("project_ids", id);
  for (const id of params.serviceLineIds ?? []) query.append("service_line_ids", id);
  for (const id of params.consultantIds ?? []) query.append("consultant_ids", id);
  for (const status of params.statuses ?? []) query.append("statuses", status);
  return apiClient.get<TimesheetReportResponse>(`/time-entries/report?${query.toString()}`);
}

export type TimesheetReportExportFormat = "pdf" | "xlsx" | "csv";

export interface TimesheetReportExportParams extends TimesheetReportParams {
  periodType: "week" | "month";
}

// Reporting screen's export — deliberately the exact same filter params as
// getTimesheetReport above, plus format/periodType, which that endpoint has no
// use for. Returns the raw Blob and the server-built filename (from
// Content-Disposition) — see lib/download.ts for turning that into an actual
// browser download.
export function exportTimesheetReport(
  format: TimesheetReportExportFormat,
  params: TimesheetReportExportParams,
) {
  const query = new URLSearchParams({
    format,
    period_type: params.periodType,
    start_date: params.startDate,
    end_date: params.endDate,
  });
  for (const id of params.projectIds ?? []) query.append("project_ids", id);
  for (const id of params.serviceLineIds ?? []) query.append("service_line_ids", id);
  for (const id of params.consultantIds ?? []) query.append("consultant_ids", id);
  for (const status of params.statuses ?? []) query.append("statuses", status);
  return apiClient.getBlob(`/time-entries/report/export?${query.toString()}`);
}
