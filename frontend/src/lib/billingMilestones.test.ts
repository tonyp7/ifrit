import { describe, expect, it, vi } from "vitest";

import {
  dueDateFromSelection,
  fitsCurrency,
  milestoneToFormValues,
  moveMilestone,
  percentFromValueInput,
  reorderOptimistically,
  typeChangeNeedsConfirmation,
  valueFromPercentInput,
} from "@/lib/billingMilestones";
import type { BillingMilestone } from "@/types/project";

function milestone(id: string, value = "100.0000"): BillingMilestone {
  return {
    id,
    project_id: "p",
    description: `Milestone ${id}`,
    due_date: null,
    value,
    position: 0,
  };
}

describe("moveMilestone", () => {
  const list = [milestone("a"), milestone("b"), milestone("c")];

  it("moves the dragged row onto the target's place", () => {
    expect(moveMilestone(list, "c", "a").map((m) => m.id)).toEqual(["c", "a", "b"]);
    expect(moveMilestone(list, "a", "b").map((m) => m.id)).toEqual(["b", "a", "c"]);
  });

  it("leaves the list alone for a drop on itself or an unknown row", () => {
    expect(moveMilestone(list, "a", "a")).toBe(list);
    expect(moveMilestone(list, "a", "zzz")).toBe(list);
  });
});

describe("reorderOptimistically", () => {
  const list = [milestone("a"), milestone("b"), milestone("c")];

  it("shows the new order and saves the full id list", async () => {
    const save = vi.fn().mockResolvedValue([]);
    const show = vi.fn();
    await reorderOptimistically(list, "c", "a", save, show);
    expect(show).toHaveBeenCalledTimes(1);
    expect(show.mock.calls[0][0].map((m: BillingMilestone) => m.id)).toEqual(["c", "a", "b"]);
    expect(save).toHaveBeenCalledWith(["c", "a", "b"]);
  });

  it("goes back to the previous order when saving fails", async () => {
    const failure = new Error("409");
    const save = vi.fn().mockRejectedValue(failure);
    const show = vi.fn();
    await expect(reorderOptimistically(list, "c", "a", save, show)).rejects.toBe(failure);
    expect(show).toHaveBeenCalledTimes(2);
    expect(show.mock.calls[1][0]).toBe(list);
  });

  it("saves nothing when the row is dropped where it was", async () => {
    const save = vi.fn();
    const show = vi.fn();
    await reorderOptimistically(list, "b", "b", save, show);
    expect(save).not.toHaveBeenCalled();
    expect(show).not.toHaveBeenCalled();
  });
});

describe("typeChangeNeedsConfirmation", () => {
  it("asks when a Fixed Price project with milestones changes type", () => {
    expect(typeChangeNeedsConfirmation("fixed_price", "time_and_material", 3)).toBe(true);
    expect(typeChangeNeedsConfirmation("fixed_price", "capped_tm", 1)).toBe(true);
  });

  it("does not ask without milestones, or when Fixed Price is kept or chosen", () => {
    expect(typeChangeNeedsConfirmation("fixed_price", "capped_tm", 0)).toBe(false);
    expect(typeChangeNeedsConfirmation("fixed_price", "fixed_price", 3)).toBe(false);
    expect(typeChangeNeedsConfirmation("time_and_material", "fixed_price", 3)).toBe(false);
  });
});

describe("dialog % and value fields", () => {
  it("fills the value from a percentage, rounded to the currency", () => {
    expect(valueFromPercentInput("33.33", "10000.0000", 2)).toBe("3333.00");
    expect(valueFromPercentInput("33.33", "1000000.0000", 0)).toBe("333300");
  });

  it("fills the percentage from a value, accepting grouped input", () => {
    expect(percentFromValueInput("2,500.00", "10000.0000")).toBe("25.00");
  });

  it("leaves the other field empty while the input is not a number", () => {
    expect(valueFromPercentInput("", "10000", 2)).toBe("");
    expect(valueFromPercentInput("12.", "10000", 2)).toBe("");
    expect(percentFromValueInput("-5", "10000")).toBe("");
  });

  it("has no percentage without a contract value", () => {
    expect(percentFromValueInput("2500", "0.0000")).toBe("");
  });

  it("checks decimals against the currency, ignoring trailing zeros", () => {
    expect(fitsCurrency("100.5", 0)).toBe(false);
    expect(fitsCurrency("100.00", 0)).toBe(true);
    expect(fitsCurrency("10.555", null)).toBe(false);
    expect(fitsCurrency("10.55", null)).toBe(true);
  });
});

describe("milestoneToFormValues", () => {
  it("shows the stored value at the currency's precision and recomputes the %", () => {
    const values = milestoneToFormValues(milestone("a", "21600.0000"), "80000.0000", 2);
    expect(values.value).toBe("21600.00");
    expect(values.percent).toBe("27.00");
  });

  it("rounds a value stored under a previous currency", () => {
    const values = milestoneToFormValues(milestone("a", "100.5000"), "1000.0000", 0);
    expect(values.value).toBe("101");
  });
});

describe("dueDateFromSelection", () => {
  it("keeps the picked calendar day", () => {
    expect(dueDateFromSelection(new Date(2027, 0, 15))).toBe("2027-01-15");
    // Local midnight on the 1st: an ISO/UTC conversion would give the previous day
    // anywhere east of UTC.
    expect(dueDateFromSelection(new Date(2027, 2, 1, 0, 0))).toBe("2027-03-01");
  });

  it("is empty once cleared", () => {
    expect(dueDateFromSelection(undefined)).toBeNull();
  });
});
