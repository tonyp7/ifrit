import { describe, expect, it } from "vitest";

import {
  differsFromContract,
  milestoneDecimals,
  percentToValue,
  roundDecimal,
  sumValues,
  valueToPercent,
} from "@/lib/milestoneMath";

describe("percentToValue", () => {
  it("rounds to cents for a two-decimal currency", () => {
    expect(percentToValue("10000.00", "33.33", 2)).toBe("3333.00");
  });

  it("rounds to whole units for a zero-decimal currency", () => {
    expect(percentToValue("1000000", "33.33", 0)).toBe("333300");
  });

  it("keeps three decimals for a three-decimal currency", () => {
    expect(percentToValue("1000.000", "33.3333", 3)).toBe("333.333");
  });

  it("treats a currency without a minor unit as two decimals", () => {
    expect(percentToValue("100", "12.345", null)).toBe("12.35");
  });

  it("rounds a half away from zero", () => {
    // 0.5% of 1 = 0.005, exactly half a cent.
    expect(percentToValue("1", "0.5", 2)).toBe("0.01");
    expect(percentToValue("1", "0.4", 2)).toBe("0.00");
  });

  it("has no float drift", () => {
    expect(percentToValue("72000.00", "30", 2)).toBe("21600.00");
    expect(percentToValue("0.30", "10", 2)).toBe("0.03");
  });

  it("returns null for input that is not a number", () => {
    expect(percentToValue("10000", "abc", 2)).toBeNull();
  });
});

describe("valueToPercent", () => {
  it("gives the share with two decimals", () => {
    expect(valueToPercent("2500.00", "10000.00")).toBe("25.00");
    expect(valueToPercent("21600.00", "80000.00")).toBe("27.00");
    expect(valueToPercent("1", "3")).toBe("33.33");
  });

  it("has nothing to compute against a zero contract value", () => {
    expect(valueToPercent("100", "0")).toBeNull();
    expect(valueToPercent("100", "0.0000")).toBeNull();
  });
});

describe("roundDecimal", () => {
  it("rounds half away from zero to the given places", () => {
    expect(roundDecimal("100.5", 0)).toBe("101");
    expect(roundDecimal("100.4", 0)).toBe("100");
    expect(roundDecimal("100.5000", 0)).toBe("101");
  });

  it("pads to the given places", () => {
    expect(roundDecimal("7", 2)).toBe("7.00");
  });
});

describe("sumValues and differsFromContract", () => {
  it("adds exactly across scales", () => {
    expect(sumValues(["0.1", "0.2"])).toBe("0.3");
    expect(sumValues(["21600.0000", "28800.00", "14400"])).toBe("64800.0000");
    expect(sumValues([])).toBe("0");
  });

  it("flags a total below or above the contract value", () => {
    expect(differsFromContract("64800.00", "72000.0000", 2)).toBe(true);
    expect(differsFromContract("80000.00", "72000.0000", 2)).toBe(true);
  });

  it("ignores differences below the currency's precision", () => {
    expect(differsFromContract("72000.00", "72000.0000", 2)).toBe(false);
    expect(differsFromContract("72000.001", "72000.0000", 2)).toBe(false);
    expect(differsFromContract("1000.4", "1000", 0)).toBe(false);
  });
});

describe("milestoneDecimals", () => {
  it("falls back to two decimals", () => {
    expect(milestoneDecimals(null)).toBe(2);
    expect(milestoneDecimals(undefined)).toBe(2);
    expect(milestoneDecimals(0)).toBe(0);
  });
});
