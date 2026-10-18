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

describe("tax warnings", () => {
  const base = { quantities: [], payeeCurrency: "EUR", invoiceCurrency: "EUR" };

  it("flags a hand-set amount whose rate cannot be worked out", () => {
    expect(
      codes(
        formWarnings({
          ...base,
          subtotal: "0.00",
          taxes: [{ amount_set_by_hand: true, rate: null, amount: "10.00" }],
        }),
      ),
    ).toEqual(["tax_rate_not_derivable"]);
    expect(
      formWarnings({
        ...base,
        subtotal: "100.00",
        taxes: [{ amount_set_by_hand: true, rate: "10.000", amount: "10.00" }],
      }),
    ).toEqual([]);
  });

  it("flags a negative subtotal, not a zero one", () => {
    expect(codes(formWarnings({ ...base, subtotal: "-500.00" }))).toEqual([
      "negative_subtotal",
    ]);
    expect(formWarnings({ ...base, subtotal: "0.00" })).toEqual([]);
  });

  it("lets the live values replace the server's tax warnings", () => {
    const server: InvoiceWarning[] = [
      { code: "negative_subtotal", service_lines: [], companies: [] },
    ];
    expect(combineWarnings([], server)).toEqual([]);
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
