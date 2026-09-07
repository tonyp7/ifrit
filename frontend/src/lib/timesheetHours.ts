export function cellKey(serviceLineId: string, dayKey: string): string {
  return `${serviceLineId}__${dayKey}`;
}

// Renders a stored/edited hours value in its shortest form (e.g. "1.50" -> "1.5",
// "2.00" -> "2") — used both for totals and for the value shown back in a cell after
// a blur-save round-trip.
export function formatHours(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "";
  return value % 1 === 0 ? String(value) : value.toFixed(1);
}

// Blur-time correction (see specs/requirements/timesheet.md#interactions--input-rules:
// "reject/ignore out-of-range or non-numeric input rather than throwing"): empty ->
// "0" (triggers delete-on-zero), invalid -> revert to fallback, otherwise clamp to
// 0-24 and round to the nearest 0.5.
export function normalizeHours(raw: string, fallback: string): string {
  const trimmed = raw.trim();
  if (trimmed === "") return "0";
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return fallback || "0";
  const clamped = Math.min(24, Math.max(0, parsed));
  const rounded = Math.round(clamped * 2) / 2;
  return String(rounded);
}

export function sumHours(values: Array<string | undefined>): number {
  return values.reduce((sum: number, v) => sum + (v ? Number(v) : 0), 0);
}
