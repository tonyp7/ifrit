// Fixed rotating palette for service-line rows (see
// specs/requirements/timesheet.md#interactions--input-rules — "Add service line...
// assigns the next color from a fixed rotating palette"). Assignment is purely
// positional (a row's color = its index in the current `serviceLines` array), so no
// separate assignment state needs to be tracked or persisted.
const SERVICE_LINE_BORDER_COLORS = [
  "border-l-blue-500",
  "border-l-emerald-500",
  "border-l-amber-500",
  "border-l-fuchsia-500",
  "border-l-cyan-500",
  "border-l-rose-500",
  "border-l-lime-500",
  "border-l-indigo-500",
] as const;

export function serviceLineBorderColor(index: number): string {
  return SERVICE_LINE_BORDER_COLORS[index % SERVICE_LINE_BORDER_COLORS.length];
}
