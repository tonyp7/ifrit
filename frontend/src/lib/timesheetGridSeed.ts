import { cellKey, formatHours } from "@/lib/timesheetHours";
import type {
  EntryCell,
  ServiceLineRow,
  TimeEntry,
  TimesheetReportRow,
} from "@/types/timesheet";

// The local, editable state a timesheet grid starts from for one set of fetched entries. Pure
// so the hooks can build it both for their first render and whenever their input is replaced,
// without an effect that would render once with the old state first.

export interface TimesheetGridSeed {
  entries: Record<string, EntryCell>;
  // One row per service line that has at least one entry, in the order first met.
  historicalServiceLines: ServiceLineRow[];
}

// My Timesheet: every entry belongs to `rowOwnerId`.
export function seedTimesheetGrid(
  initialEntries: TimeEntry[],
  rowOwnerId: string,
): TimesheetGridSeed {
  const entries: Record<string, EntryCell> = {};
  const seen = new Set<string>();
  const historicalServiceLines: ServiceLineRow[] = [];
  for (const item of initialEntries) {
    entries[cellKey(rowOwnerId, item.service_line_id, item.date)] = {
      hours: formatHours(Number(item.hours)),
      is_locked: item.is_locked,
    };
    if (!seen.has(item.service_line_id)) {
      seen.add(item.service_line_id);
      historicalServiceLines.push({
        service_line_id: item.service_line_id,
        service_line_name: item.service_line_name,
        project_id: item.project_id,
        project_name: item.project_name,
        user_id: rowOwnerId,
      });
    }
  }
  return { entries, historicalServiceLines };
}

export interface ReportGridSeed {
  entries: Record<string, EntryCell>;
  // Keyed `${user_id}__${service_line_id}`.
  assignedByPair: Record<string, boolean>;
  projectStatusByPair: Record<string, string>;
}

// Reporting: one row per (consultant, service line) pair, each carrying its own entries.
export function seedReportGrid(rows: TimesheetReportRow[]): ReportGridSeed {
  const entries: Record<string, EntryCell> = {};
  const assignedByPair: Record<string, boolean> = {};
  const projectStatusByPair: Record<string, string> = {};
  for (const row of rows) {
    const pairKey = `${row.user_id}__${row.service_line_id}`;
    assignedByPair[pairKey] = row.is_assigned;
    projectStatusByPair[pairKey] = row.project_status;
    for (const item of row.entries) {
      entries[cellKey(row.user_id, item.service_line_id, item.date)] = {
        hours: formatHours(Number(item.hours)),
        is_locked: item.is_locked,
      };
    }
  }
  return { entries, assignedByPair, projectStatusByPair };
}
