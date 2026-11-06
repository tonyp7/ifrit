import { describe, expect, it } from "vitest";

import {
  billedForLabel,
  formatPeriod,
  generationPeriodFor,
  isValidPeriod,
  presetRange,
} from "@/lib/invoicePeriods";
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

describe("generationPeriodFor", () => {
  const today = new Date(2026, 9, 14);

  it("opens on the Last month preset when the draft has no period", () => {
    expect(generationPeriodFor({ start: null, end: null }, today)).toEqual({
      preset: "last_month",
      start: "2026-09-01",
      end: "2026-09-30",
    });
  });

  it("opens on the draft's own period, with no preset highlighted", () => {
    expect(generationPeriodFor({ start: "2026-08-01", end: "2026-08-31" }, today)).toEqual({
      preset: null,
      start: "2026-08-01",
      end: "2026-08-31",
    });
  });

  it("ignores half a period", () => {
    expect(generationPeriodFor({ start: "2026-08-01", end: null }, today).preset).toBe(
      "last_month",
    );
  });
});

describe("billedForLabel", () => {
  const none = { start: null, end: null };

  it("is the period when the draft has one, whatever its lines say", () => {
    expect(billedForLabel({ start: "2026-09-01", end: "2026-09-30" }, ["Custom line"])).toBe(
      formatPeriod(new Date(2026, 8, 1), new Date(2026, 8, 30)),
    );
  });

  it("is the line descriptions in order, joined, when there is no period", () => {
    expect(billedForLabel(none, ["Downpayment", "End of SIT"])).toBe(
      "Downpayment, End of SIT",
    );
  });

  it("is the one line of an invoice built by hand", () => {
    expect(billedForLabel(none, ["Custom Invoice Line"])).toBe("Custom Invoice Line");
  });

  it("skips blank descriptions and trims the others", () => {
    expect(billedForLabel(none, ["  Travel ", "", "   ", "Hotel"])).toBe("Travel, Hotel");
  });

  it("is nothing with no period and no line, or only blank ones", () => {
    expect(billedForLabel(none, [])).toBeNull();
    expect(billedForLabel(none, ["", "  "])).toBeNull();
  });

  it("ignores half a period", () => {
    expect(billedForLabel({ start: "2026-09-01", end: null }, ["Custom line"])).toBe(
      "Custom line",
    );
  });
});
