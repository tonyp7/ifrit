import { WORKDAY_MAX_SECONDS, WORKDAY_MIN_SECONDS } from "@/types/settings";

export interface DurationParts {
  hours: number;
  minutes: number;
  seconds: number;
}

/** Highest value each field accepts: 24 hours, so a full day can be entered. */
export const PART_MAX: DurationParts = { hours: 24, minutes: 59, seconds: 59 };

export function splitDuration(total: number): DurationParts {
  return {
    hours: Math.floor(total / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
  };
}

/**
 * Parses what a field holds: anything that is not a whole number of zero or more counts as
 * 0, and a value above the field's maximum is lowered to it.
 */
export function parsePart(raw: string, max: number): number {
  const value = /^\d+$/.test(raw.trim()) ? Number(raw.trim()) : 0;
  return Math.min(value, max);
}

/** Seconds for the parts, brought within the allowed workday range. */
export function joinDuration(parts: DurationParts): number {
  const total =
    Math.min(parts.hours, PART_MAX.hours) * 3600 +
    Math.min(parts.minutes, PART_MAX.minutes) * 60 +
    Math.min(parts.seconds, PART_MAX.seconds);
  return Math.min(WORKDAY_MAX_SECONDS, Math.max(WORKDAY_MIN_SECONDS, total));
}

/** `hh:mm:ss`, as the card's helper text shows it. */
export function formatDuration(total: number): string {
  const { hours, minutes, seconds } = splitDuration(total);
  return [hours, minutes, seconds].map((n) => String(n).padStart(2, "0")).join(":");
}
