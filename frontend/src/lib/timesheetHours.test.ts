import { describe, expect, it } from "vitest";

import { isUnchangedHours, normalizeHours } from "./timesheetHours";

describe("isUnchangedHours", () => {
  it("is true when the value is the same as on focus", () => {
    expect(isUnchangedHours("4", "4")).toBe(true);
    expect(isUnchangedHours("1.5", "1.5")).toBe(true);
  });

  it("treats an empty cell and zero as the same value", () => {
    // A cell that was empty on focus and is still empty normalizes to "0".
    expect(isUnchangedHours("", "0")).toBe(true);
  });

  it("is false when the value changed", () => {
    expect(isUnchangedHours("4", "5")).toBe(false);
    expect(isUnchangedHours("", "2")).toBe(false);
    // Clearing a saved entry is a change (it deletes it).
    expect(isUnchangedHours("4", "0")).toBe(false);
  });

  it("compares the normalized value, so an edit that rounds back is unchanged", () => {
    expect(isUnchangedHours("1.5", normalizeHours("1.6", "1.5"))).toBe(true);
  });

  it("is false when the focus value is unknown, so the save still happens", () => {
    expect(isUnchangedHours(undefined, "0")).toBe(false);
    expect(isUnchangedHours(undefined, "4")).toBe(false);
  });
});
