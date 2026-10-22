import { describe, expect, it } from "vitest";

import { PAYMENT_MEANS_LABELS } from "@/types/company";

describe("PAYMENT_MEANS_LABELS", () => {
  // The same words the invoice PDF prints for these codes.
  it("names the three payment means for the payee account form and table", () => {
    expect(PAYMENT_MEANS_LABELS).toEqual({
      "30": "Wire transfer",
      "42": "Bank transfer",
      "58": "SEPA credit transfer",
    });
  });
});
