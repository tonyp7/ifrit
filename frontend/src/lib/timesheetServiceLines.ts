import type { ServiceLineRow } from "@/types/timesheet";

// Ascending by project name, then service line name: a stable, identity-based
// order applied to the whole `serviceLines` union regardless of how each line
// entered it (manually added vs. discovered via time_entries history) or which
// period's date window was last fetched. This replaces fetch-order (which
// differed between Week and Month, since they load different date ranges) as
// the source of row order.
export function sortServiceLines(lines: ServiceLineRow[]): ServiceLineRow[] {
  return [...lines].sort(
    (a, b) =>
      a.project_name.localeCompare(b.project_name) ||
      (a.service_line_name ?? "").localeCompare(b.service_line_name ?? ""),
  );
}

// The "add a service line" guidance only makes sense when the user has no rows yet and
// there is at least one line they could actually add. A user with nothing eligible (not
// assigned anywhere, or never assignable) gets no text, and Reporting, which passes no
// add options at all, never gets it.
export function shouldShowAddLineHint(
  displayedRowCount: number,
  addOptionCount: number | undefined,
): boolean {
  return displayedRowCount === 0 && (addOptionCount ?? 0) > 0;
}
