import { addDays, startOfMonth, startOfWeekMonday } from "@/lib/timesheetDates";

export type PeriodPreset = "this_month" | "last_month" | "this_week" | "last_week";

export const PERIOD_PRESETS: PeriodPreset[] = [
  "this_month",
  "last_month",
  "this_week",
  "last_week",
];

export const PERIOD_PRESET_LABELS: Record<PeriodPreset, string> = {
  this_month: "This month",
  last_month: "Last month",
  this_week: "This week",
  last_week: "Last week",
};

// Matches the server's limit: a year of monthly invoicing can be fixed in one go, a
// mistyped year cannot sum a decade of time entries.
export const MAX_PERIOD_DAYS = 366;

export interface DateRange {
  start: Date;
  end: Date;
}

/** The days a preset covers on `today`. Weeks run Monday to Sunday, like the timesheet,
 * so a week preset covers exactly the days a consultant sees. */
export function presetRange(preset: PeriodPreset, today: Date): DateRange {
  switch (preset) {
    case "this_month": {
      const start = startOfMonth(today);
      return { start, end: new Date(start.getFullYear(), start.getMonth() + 1, 0) };
    }
    case "last_month": {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      return { start, end: new Date(start.getFullYear(), start.getMonth() + 1, 0) };
    }
    case "this_week": {
      const start = startOfWeekMonday(today);
      return { start, end: addDays(start, 6) };
    }
    case "last_week": {
      const start = addDays(startOfWeekMonday(today), -7);
      return { start, end: addDays(start, 6) };
    }
  }
}

function dayNumber(d: Date): number {
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86_400_000;
}

/** Whether a range can be invoiced: in order and at most MAX_PERIOD_DAYS long. */
export function isValidPeriod(range: DateRange): boolean {
  const length = dayNumber(range.end) - dayNumber(range.start) + 1;
  return length >= 1 && length <= MAX_PERIOD_DAYS;
}

/** A period as people read it, e.g. "1–30 Sep 2026", in the user's language. */
export function formatPeriod(start: Date, end: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).formatRange(start, end);
}
