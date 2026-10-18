import { describe, expect, it } from "vitest";

import {
  computeTaxes,
  displayRate,
  isTaxBaseMode,
  labelChange,
  totalWithTaxes,
  type TaxBaseMode,
  type TaxRowInput,
} from "@/lib/invoiceTaxes";

function rate(value: string, mode: TaxBaseMode = "subtotal"): TaxRowInput {
  return { base_mode: mode, rate: value, amount: "", amount_set_by_hand: false };
}

function byHand(value: string, mode: TaxBaseMode = "subtotal"): TaxRowInput {
  return { base_mode: mode, rate: "", amount: value, amount_set_by_hand: true };
}

// The same worked example the server's tests run.
const EXAMPLE = [rate("5"), rate("9.975", "cumulative"), byHand("100.00")];

describe("computeTaxes", () => {
  it("runs the worked example", () => {
    const [gst, qst, eco] = computeTaxes("19037.50", EXAMPLE, 2);
    expect(gst).toEqual({
      baseMode: "subtotal",
      base: "19037.50",
      rate: "5",
      amount: "951.88",
    });
    expect(qst).toEqual({
      baseMode: "cumulative",
      base: "19989.38",
      rate: "9.975",
      amount: "1993.94",
    });
    expect(eco).toEqual({
      baseMode: "subtotal",
      base: "19037.50",
      rate: "0.525",
      amount: "100.00",
    });
    expect(totalWithTaxes("19037.50", [gst, qst, eco], 2)).toBe("22083.32");
  });

  it("puts the first row on the subtotal", () => {
    const [first] = computeTaxes("19037.50", [rate("5", "cumulative")], 2);
    expect(first.baseMode).toBe("subtotal");
    expect(first.base).toBe("19037.50");
  });

  it("has no rate for a hand-set amount on a zero base", () => {
    const [row] = computeTaxes("0.00", [byHand("10.00")], 2);
    expect(row.rate).toBeNull();
    expect(row.amount).toBe("10.00");
  });

  it("treats a rate too large to store as unknown", () => {
    const [row] = computeTaxes("0.01", [byHand("99999999.00")], 2);
    expect(row.rate).toBeNull();
  });

  it("gives negative amounts on a negative subtotal", () => {
    const [row] = computeTaxes("-500.00", [rate("10")], 2);
    expect(row.amount).toBe("-50.00");
  });

  it("recomputes compounding rows after a reorder", () => {
    const [qst, gst] = computeTaxes("19037.50", [rate("9.975"), rate("5", "cumulative")], 2);
    expect(qst.amount).toBe("1898.99");
    expect(gst.base).toBe("20936.49");
    expect(gst.amount).toBe("1046.82");
  });

  it("keeps a hand-set amount and lowers its rate when the subtotal grows", () => {
    const [gst, eco] = computeTaxes("25000.00", [rate("5"), byHand("100.00")], 2);
    expect(gst.amount).toBe("1250.00");
    expect(eco.amount).toBe("100.00");
    expect(eco.rate).toBe("0.400");
  });

  it("rounds to the currency's decimals", () => {
    expect(computeTaxes("333", [rate("10")], 0)[0].amount).toBe("33");
  });

  it("leaves a row it cannot read out of the sums", () => {
    const rows = computeTaxes("100.00", [rate(""), rate("10", "cumulative")], 2);
    expect(rows[0]).toMatchObject({ rate: null, amount: null });
    expect(rows[1]).toMatchObject({ base: "100.00", amount: "10.00" });
    expect(totalWithTaxes("100.00", rows, 2)).toBe("110.00");
  });
});

describe("isTaxBaseMode", () => {
  it("accepts the two choices and refuses the empty value a remounted dropdown reports", () => {
    expect(isTaxBaseMode("subtotal")).toBe(true);
    expect(isTaxBaseMode("cumulative")).toBe(true);
    expect(isTaxBaseMode("")).toBe(false);
    expect(isTaxBaseMode("toString")).toBe(false);
  });
});

describe("labelChange", () => {
  it("sets a 0 % rate for Zero-Rate and Tax-Exempt", () => {
    expect(labelChange("Zero-Rate", true)).toEqual({
      label: "Zero-Rate",
      rate: "0",
      amount_set_by_hand: false,
    });
    expect(labelChange("Tax-Exempt", true)).toMatchObject({ rate: "0" });
  });

  it("leaves the rate alone for other presets and typed labels", () => {
    expect(labelChange("VAT", true)).toEqual({ label: "VAT" });
    expect(labelChange("Eco levy", false)).toEqual({ label: "Eco levy" });
    expect(labelChange("Zero-Rate", false)).toEqual({ label: "Zero-Rate" });
  });
});

describe("displayRate", () => {
  it("drops trailing zeros", () => {
    expect(displayRate("5.000")).toBe("5");
    expect(displayRate("0.400")).toBe("0.4");
    expect(displayRate("9.975")).toBe("9.975");
    expect(displayRate("12")).toBe("12");
  });
});
