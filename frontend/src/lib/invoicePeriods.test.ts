import { describe, expect, it } from "vitest";

import { isValidPeriod, presetRange } from "@/lib/invoicePeriods";
import { toDayKey } from "@/lib/timesheetDates";

// Wednesday 14 Oct 2026.
const today = new Date(2026, 9, 14);

function keys(preset: Parameters<typeof presetRange>[0], on = today) {
  const { start, end } = presetRange(preset, on);
  return [toDayKey(start), toDayKey(end)];
}

describe("period presets", () => {
  it("covers this month and last month", () => {
    expect(keys("this_month")).toEqual(["2026-10-01", "2026-10-31"]);
    expect(keys("last_month")).toEqual(["2026-09-01", "2026-09-30"]);
  });

  it("crosses the year for last month in January", () => {
    expect(keys("last_month", new Date(2027, 0, 5))).toEqual(["2026-12-01", "2026-12-31"]);
  });

  it("runs weeks Monday to Sunday", () => {
    expect(keys("this_week")).toEqual(["2026-10-12", "2026-10-18"]);
    expect(keys("last_week")).toEqual(["2026-10-05", "2026-10-11"]);
  });

  it("treats Sunday as the end of its week", () => {
    expect(keys("this_week", new Date(2026, 9, 18))).toEqual(["2026-10-12", "2026-10-18"]);
  });
});

describe("isValidPeriod", () => {
  it("accepts up to 366 days in order", () => {
    expect(isValidPeriod({ start: new Date(2024, 0, 1), end: new Date(2024, 11, 31) })).toBe(
      true,
    );
    expect(isValidPeriod({ start: new Date(2026, 8, 1), end: new Date(2026, 8, 1) })).toBe(
      true,
    );
  });

  it("refuses a longer or reversed period", () => {
    expect(isValidPeriod({ start: new Date(2025, 0, 1), end: new Date(2026, 0, 2) })).toBe(
      false,
    );
    expect(isValidPeriod({ start: new Date(2026, 8, 30), end: new Date(2026, 8, 1) })).toBe(
      false,
    );
  });
});
