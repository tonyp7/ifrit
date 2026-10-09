import { describe, expect, it } from "vitest";

import { lockedCellClass, serviceLineBorderColor } from "@/lib/timesheetColors";

describe("lockedCellClass", () => {
  it("gives weekdays and weekends different classes", () => {
    expect(lockedCellClass(false)).not.toBe(lockedCellClass(true));
  });

  it("never uses red, which reads as an error rather than a lock", () => {
    expect(lockedCellClass(false)).not.toMatch(/red/);
    expect(lockedCellClass(true)).not.toMatch(/red/);
  });
});

describe("serviceLineBorderColor", () => {
  it("wraps around the palette", () => {
    expect(serviceLineBorderColor(8)).toBe(serviceLineBorderColor(0));
  });
});
