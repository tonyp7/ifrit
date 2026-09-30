import { describe, expect, it } from "vitest";

import { shouldShowAddLineHint } from "@/lib/timesheetServiceLines";

describe("shouldShowAddLineHint", () => {
  it("is true with no rows and at least one line to add", () => {
    expect(shouldShowAddLineHint(0, 1)).toBe(true);
    expect(shouldShowAddLineHint(0, 5)).toBe(true);
  });

  it("is false with no rows and nothing to add", () => {
    expect(shouldShowAddLineHint(0, 0)).toBe(false);
  });

  it("is false once a row is displayed, even if more lines could be added", () => {
    expect(shouldShowAddLineHint(1, 3)).toBe(false);
  });

  it("treats a missing option count as nothing to add, as on Reporting", () => {
    expect(shouldShowAddLineHint(0, undefined)).toBe(false);
  });

  it("is false when there are rows and nothing to add", () => {
    expect(shouldShowAddLineHint(2, 0)).toBe(false);
  });
});
