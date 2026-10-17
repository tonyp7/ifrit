import { describe, expect, it } from "vitest";

import { combineWarnings, formWarnings } from "@/lib/invoiceWarnings";
import type { InvoiceWarning } from "@/types/invoice";

const codes = (warnings: InvoiceWarning[]) => warnings.map((warning) => warning.code);

describe("formWarnings", () => {
  it("flags a zero quantity, ignoring a field still empty", () => {
    expect(
      codes(
        formWarnings({ quantities: ["0.000"], payeeCurrency: "EUR", invoiceCurrency: "EUR" }),
      ),
    ).toEqual(["zero_quantity"]);
    expect(
      formWarnings({ quantities: ["", "2"], payeeCurrency: "EUR", invoiceCurrency: "EUR" }),
    ).toEqual([]);
  });

  it("flags no payee, or a payee in another currency", () => {
    expect(
      codes(formWarnings({ quantities: [], payeeCurrency: null, invoiceCurrency: "EUR" })),
    ).toEqual(["no_payee_account"]);
    expect(
      codes(formWarnings({ quantities: [], payeeCurrency: "USD", invoiceCurrency: "EUR" })),
    ).toEqual(["payee_currency"]);
  });
});

describe("combineWarnings", () => {
  it("keeps the server's own warnings and replaces the form ones with live values", () => {
    const server: InvoiceWarning[] = [
      { code: "unlocked_hours", service_lines: [], companies: [] },
      { code: "no_payee_account", service_lines: [], companies: [] },
    ];
    expect(codes(combineWarnings([], server))).toEqual(["unlocked_hours"]);
  });
});
