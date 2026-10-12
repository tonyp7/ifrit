import type { TimesheetReportFilters } from "@/types/timesheet";

export interface ReportSelection {
  projectIds: string[];
  serviceLineIds: string[];
  consultantIds: string[];
}

function keepOffered(selected: string[], offered: string[]): string[] {
  const offeredSet = new Set(offered);
  const kept = selected.filter((id) => offeredSet.has(id));
  // Same array back when nothing was dropped, so React sees no state change and
  // the rows are not fetched again for nothing.
  return kept.length === selected.length ? selected : kept;
}

// After "Only see my projects" changes the options, a selection the new options no
// longer offer would keep narrowing the rows invisibly (no checkbox left to clear
// it), so it is dropped. Project Status is not scope-dependent and is left alone.
export function pruneSelection(
  selection: ReportSelection,
  options: TimesheetReportFilters,
): ReportSelection {
  return {
    projectIds: keepOffered(
      selection.projectIds,
      options.projects.map((p) => p.project_id),
    ),
    serviceLineIds: keepOffered(
      selection.serviceLineIds,
      options.service_lines.map((l) => l.service_line_id),
    ),
    consultantIds: keepOffered(
      selection.consultantIds,
      options.consultants.map((c) => c.user_id),
    ),
  };
}
