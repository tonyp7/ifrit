import { describe, expect, it } from "vitest";

import { dueDateFor } from "@/lib/paymentTerms";
import { toDayKey } from "@/lib/timesheetDates";
import type { PaymentTerms } from "@/types/invoice";

// The invoicing plan's table, for an invoice issued on 14 Oct 2026.
const TABLE: [PaymentTerms, string][] = [
  ["due_on_receipt", "2026-10-14"],
  ["net_7", "2026-10-21"],
  ["net_15", "2026-10-29"],
  ["net_30", "2026-11-13"],
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

  it("finds the last day of February in a leap year", () => {
    expect(toDayKey(dueDateFor("eom", new Date(2028, 1, 3)))).toBe("2028-02-29");
  });
});
