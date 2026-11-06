import { describe, expect, it } from "vitest";

import { dueDateFor } from "@/lib/paymentTerms";
import { toDayKey } from "@/lib/timesheetDates";
import { PAYMENT_TERMS, PAYMENT_TERMS_LABELS, type PaymentTerms } from "@/types/invoice";
import invoices from "../../public/locales/en/invoices.json";

// The invoicing plan's table, for an invoice issued on 14 Oct 2026.
const TABLE: [PaymentTerms, string][] = [
  ["due_on_receipt", "2026-10-14"],
  ["net_7", "2026-10-21"],
  ["net_15", "2026-10-29"],
  ["net_30", "2026-11-13"],
  ["net_45", "2026-11-28"],
  ["net_60", "2026-12-13"],
  ["net_90", "2027-01-12"],
  ["eom", "2026-10-31"],
  ["eom_15", "2026-11-15"],
  ["eom_30", "2026-11-30"],
  ["eom_60", "2026-12-30"],
  ["eom_90", "2027-01-29"],
];

describe("dueDateFor", () => {
  it.each(TABLE)("%s from 14 Oct 2026 is %s", (preset, expected) => {
    expect(toDayKey(dueDateFor(preset, new Date(2026, 9, 14)))).toBe(expected);
  });

  it("rolls Net 45 over a month and a year end", () => {
    expect(toDayKey(dueDateFor("net_45", new Date(2026, 11, 20)))).toBe("2027-02-03");
  });

  it("finds the last day of February in a leap year", () => {
    expect(toDayKey(dueDateFor("eom", new Date(2028, 1, 3)))).toBe("2028-02-29");
  });
});

describe("the payment terms list", () => {
  it("offers Net 45 after Net 30 and before Net 60", () => {
    const labels = PAYMENT_TERMS.map((preset) => PAYMENT_TERMS_LABELS[preset]);
    expect(labels.indexOf("Net 45")).toBe(labels.indexOf("Net 30") + 1);
    expect(labels.indexOf("Net 60")).toBe(labels.indexOf("Net 45") + 1);
  });

  it("has an English locale entry for every label", () => {
    const entries = invoices as Record<string, string>;
    for (const label of Object.values(PAYMENT_TERMS_LABELS)) {
      expect(entries[label], label).toBeDefined();
    }
  });
});
