// Fixed rotating palette for service-line rows: adding a new one assigns the next
// color in the list. Assignment is purely positional (a row's color = its index in
// the current `serviceLines` array), so no separate assignment state needs to be
// tracked or persisted.
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

// Locked cells share one look across the desktop grid and the mobile view. The weekend
// variant is a step stronger, so a locked Saturday/Sunday still reads as a weekend. The
// classes are custom utilities defined in index.css.
export function lockedCellClass(weekend: boolean): string {
  return weekend ? "locked-cell-weekend" : "locked-cell";
}
