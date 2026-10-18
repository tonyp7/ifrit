import { describe, expect, it } from "vitest";

import { lineAmount, subtotal } from "@/lib/invoiceMath";

describe("invoice amounts", () => {
  it("rounds half away from zero to the currency's decimals", () => {
    expect(lineAmount("1.42857", "700", 2)).toBe("1000.00");
    expect(lineAmount("2.5", "333", 0)).toBe("833");
    expect(lineAmount("152.5", "95", 2)).toBe("14487.50");
  });

  it("rounds a negative amount away from zero too", () => {
    expect(lineAmount("1", "-0.125", 2)).toBe("-0.13");
    expect(lineAmount("1", "-250", 2)).toBe("-250.00");
  });

  it("uses 2 decimals for a currency with none defined", () => {
    expect(lineAmount("1", "10.005", null)).toBe("10.01");
  });

  it("is null while a field is not a number", () => {
    expect(lineAmount("", "95", 2)).toBeNull();
    expect(lineAmount("1,5", "95", 2)).toBeNull();
  });

  it("sums the computable lines", () => {
    const lines = [
      { quantity: "152.5", unit_price: "95" },
      { quantity: "40", unit_price: "120" },
      { quantity: "1", unit_price: "-250" },
      { quantity: "abc", unit_price: "1" },
    ];
    expect(subtotal(lines, 2)).toBe("19037.50");
    expect(subtotal([], 0)).toBe("0");
  });
});
