import { describe, expect, it } from "vitest";

import { appendGeneratedLines } from "@/components/invoices/invoiceForm";
import type { GeneratedLine } from "@/types/invoice";

const existing = [
  {
    key: "a",
    description: "Hand-edited",
    quantity: "3",
    uom: "ea" as const,
    unit_price: "10",
  },
  { key: "b", description: "Travel", quantity: "1", uom: "ea" as const, unit_price: "42.5" },
];

const generated: GeneratedLine[] = [
  { name: "Senior developer", quantity: "152.50000", uom: "hours", unit_price: "95.0000" },
  { name: "Tester", quantity: "2.00000", uom: "days", unit_price: "400.0000" },
];

const describe_ = (line: GeneratedLine) => `${line.name} — Sep`;

describe("appendGeneratedLines", () => {
  it("keeps the existing lines untouched and in place, then adds the generated ones", () => {
    const result = appendGeneratedLines(existing, generated, describe_);
    expect(result).toHaveLength(4);
    expect(result.slice(0, 2)).toEqual(existing);
    expect(result.slice(2).map((line) => line.description)).toEqual([
      "Senior developer — Sep",
      "Tester — Sep",
    ]);
    expect(result[2]).toMatchObject({ quantity: "152.5", uom: "hours", unit_price: "95" });
  });

  it("does not change the array it was given", () => {
    const before = structuredClone(existing);
    appendGeneratedLines(existing, generated, describe_);
    expect(existing).toEqual(before);
  });

  it("fills an empty draft", () => {
    expect(appendGeneratedLines([], generated, describe_)).toHaveLength(2);
  });

  it("adds a repeated generation again, with its own keys", () => {
    const once = appendGeneratedLines(existing, generated, describe_);
    const twice = appendGeneratedLines(once, generated, describe_);
    expect(twice).toHaveLength(6);
    expect(new Set(twice.map((line) => line.key)).size).toBe(6);
  });

  it("appends milestone lines named as the contract names them", () => {
    const milestone: GeneratedLine[] = [
      { name: "Downpayment", quantity: "1.00000", uom: "ea", unit_price: "12000.0000" },
    ];
    const result = appendGeneratedLines(existing, milestone, (line) => line.name ?? "");
    expect(result.at(-1)).toMatchObject({ description: "Downpayment", quantity: "1" });
    expect(result.slice(0, 2)).toEqual(existing);
  });
});
