import type { PeriodType } from "@/types/timesheet";

// Every function here works in the browser's local timezone (plain Date
// getters/setters, never the UTC/ISO variants) — "today," day boundaries, and which
// `date` an entry lands on are deliberately local, not server/UTC time (see
// docs/requirements/timesheet.md#my-timesheet-clocking).

export function toDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseDayKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(d: Date, amount: number): Date {
  const next = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  next.setDate(next.getDate() + amount);
  return next;
}

// Monday-start week, hardcoded per ISO-8601 (see
// docs/requirements/timesheet.md#interactions--input-rules).
export function startOfWeekMonday(d: Date): Date {
  const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const mondayIndexedDay = (date.getDay() + 6) % 7; // Mon=0 ... Sun=6
  date.setDate(date.getDate() - mondayIndexedDay);
  return date;
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function getPeriodDays(periodType: PeriodType, periodDate: Date): Date[] {
  if (periodType === "week") {
    const start = startOfWeekMonday(periodDate);
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
  }
  const start = startOfMonth(periodDate);
  const daysInMonth = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate();
  return Array.from({ length: daysInMonth }, (_, i) => addDays(start, i));
}

export function shiftPeriod(
  periodType: PeriodType,
  periodDate: Date,
  direction: 1 | -1,
): Date {
  if (periodType === "week") {
    return addDays(periodDate, 7 * direction);
  }
  return new Date(periodDate.getFullYear(), periodDate.getMonth() + direction, 1);
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function isToday(d: Date): boolean {
  return isSameDay(d, new Date());
}

export function isWeekend(d: Date): boolean {
  const day = d.getDay();
  return day === 0 || day === 6;
}

// Standard ISO-8601 week-number algorithm: the week containing the year's first
// Thursday is week 1.
export function getIsoWeekNumber(d: Date): number {
  const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const mondayIndexedDay = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - mondayIndexedDay + 3);
  const firstThursday = new Date(date.getFullYear(), 0, 4);
  const firstThursdayMondayIndexed = (firstThursday.getDay() + 6) % 7;
  firstThursday.setDate(firstThursday.getDate() - firstThursdayMondayIndexed + 3);
  return 1 + Math.round((date.getTime() - firstThursday.getTime()) / (7 * 86400000));
}

export function formatMonthLabel(d: Date): string {
  return new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(d);
}

export function formatWeekdayShort(d: Date): string {
  return new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(d).slice(0, 3);
}

// Single-letter weekday (M, T, W, ...) — desktop grid's Month view only (28-31
// columns need the narrower label; Week view's 7 columns use formatWeekdayShort
// above instead — see docs/requirements/timesheet.md#desktop--tablet-view).
export function formatWeekdayNarrow(d: Date): string {
  return new Intl.DateTimeFormat(undefined, { weekday: "narrow" }).format(d);
}

export function formatFullDate(d: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(d);
}
