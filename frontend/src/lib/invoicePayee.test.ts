import { describe, expect, it } from "vitest";

import {
  orderPayeeAccounts,
  payeeFormFromAccount,
  preselectPayee,
  toInvoicePayee,
} from "@/lib/invoicePayee";
import type { ContextPayeeAccount } from "@/types/invoice";

function account(id: string, currency: string, primary = false): ContextPayeeAccount {
  return {
    id,
    is_primary: primary,
    payment_means_code: "58",
    account_scheme: "iban",
    account_identifier: "BE71096123456769",
    account_name: null,
    currency_code: currency,
    bic: "GEBABEBB",
    bank_name: null,
    bank_address: null,
  };
}

describe("preselectPayee", () => {
  it("takes the primary account in the invoice currency", () => {
    expect(preselectPayee([account("1", "EUR"), account("2", "EUR", true)], "EUR")?.id).toBe(
      "2",
    );
  });

  it("takes the only account in the currency", () => {
    expect(preselectPayee([account("1", "USD", true), account("2", "EUR")], "EUR")?.id).toBe(
      "2",
    );
  });

  it("leaves it empty with several and no primary, or none in the currency", () => {
    expect(preselectPayee([account("1", "EUR"), account("2", "EUR")], "EUR")).toBeNull();
    expect(preselectPayee([account("1", "USD", true)], "EUR")).toBeNull();
  });
});

describe("orderPayeeAccounts", () => {
  it("puts the invoice currency first", () => {
    const ordered = orderPayeeAccounts(
      [account("1", "USD"), account("2", "EUR"), account("3", "GBP")],
      "EUR",
    );
    expect(ordered.map((a) => a.id)).toEqual(["2", "1", "3"]);
  });
});

describe("copying an account", () => {
  it("fills the form fields and gives back the API body without a primary flag", () => {
    const values = payeeFormFromAccount(account("1", "EUR", true));
    expect(values.account_identifier).toBe("BE71 0961 2345 6769");
    const payee = toInvoicePayee(values);
    expect(payee).toEqual({
      payment_means_code: "58",
      account_scheme: "iban",
      account_identifier: "BE71096123456769",
      account_name: null,
      currency_code: "EUR",
      bic: "GEBABEBB",
      bank_name: null,
      bank_address: null,
    });
    expect("is_primary" in payee).toBe(false);
  });
});
