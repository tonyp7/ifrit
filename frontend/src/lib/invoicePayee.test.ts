import { describe, expect, it } from "vitest";

import {
  orderPayeeAccounts,
  payeeAccountOptionLabel,
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

// The same number and currency offered two ways, as a company paid through Revolut might.
function wireAndSepa(): [ContextPayeeAccount, ContextPayeeAccount] {
  return [
    { ...account("1", "EUR"), payment_means_code: "30", bic: "REVOGB21" },
    { ...account("2", "EUR"), payment_means_code: "58", bic: "REVOLT21" },
  ];
}

describe("preselectPayee", () => {
  const pick = (accounts: ContextPayeeAccount[], currency = "EUR") =>
    preselectPayee(accounts, currency)?.id;

  it("takes the primary account in the invoice currency", () => {
    expect(pick([account("1", "EUR"), account("2", "EUR", true)])).toBe("2");
  });

  it("prefers the primary in the currency over a lower-id account in it", () => {
    expect(
      pick([account("a", "EUR"), account("b", "EUR", true), account("c", "USD", true)]),
    ).toBe("b");
  });

  it("takes a non-primary account in the currency before a primary in another", () => {
    expect(pick([account("1", "USD", true), account("2", "EUR")])).toBe("2");
  });

  it("takes the lowest id among several in the currency and no primary", () => {
    expect(pick([account("b", "EUR"), account("a", "EUR"), account("c", "EUR")])).toBe("a");
  });

  it("takes a primary in another currency when none is in the invoice currency", () => {
    expect(pick([account("1", "USD"), account("2", "HKD", true)], "JPY")).toBe("2");
  });

  it("takes the lowest id among several primaries in other currencies", () => {
    expect(
      pick([account("z", "USD", true), account("m", "HKD", true), account("a", "GBP")], "JPY"),
    ).toBe("m");
  });

  it("takes the lowest id with no primary and none in the currency", () => {
    expect(pick([account("b", "USD"), account("a", "HKD")], "JPY")).toBe("a");
  });

  it("takes the vendor's only account whatever its currency", () => {
    expect(pick([account("1", "HKD", true)], "JPY")).toBe("1");
    expect(pick([account("1", "HKD")], "JPY")).toBe("1");
  });

  it("does not depend on the order the accounts come in", () => {
    const accounts = [
      account("c", "EUR"),
      account("a", "EUR"),
      account("b", "USD", true),
      account("d", "EUR", true),
    ];
    expect(pick(accounts)).toBe("d");
    expect(pick([...accounts].reverse())).toBe("d");
    const noPrimary = [account("c", "EUR"), account("a", "EUR"), account("b", "EUR")];
    expect(pick(noPrimary)).toBe("a");
    expect(pick([...noPrimary].reverse())).toBe("a");
  });

  it("compares ids as plain strings, the order the server sorts by", () => {
    const low = "0b6f0a52-9d1e-4c7a-8d63-1f2c3d4e5f60";
    const high = "f0b6f0a5-29d1-4e4c-a7a8-d631f2c3d4e5";
    expect(pick([account(high, "EUR"), account(low, "EUR")])).toBe(low);
  });

  it("is null when the vendor has no account", () => {
    expect(preselectPayee([], "EUR")).toBeNull();
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

describe("accounts that share an identifier", () => {
  const words = (account: ContextPayeeAccount) => ({
    means: account.payment_means_code === "30" ? "Wire transfer" : "SEPA credit transfer",
    primary: "primary",
  });

  it("are listed with their payment means, so they can be told apart", () => {
    const [wire, sepa] = wireAndSepa();
    const labels = [wire, sepa].map((a) => payeeAccountOptionLabel(a, words(a)));
    expect(labels).toEqual([
      "BE71 0961 2345 6769, Wire transfer (EUR)",
      "BE71 0961 2345 6769, SEPA credit transfer (EUR)",
    ]);
    expect(new Set(labels).size).toBe(2);
  });

  it("show whether one is the primary of its currency", () => {
    const [wire] = wireAndSepa();
    expect(payeeAccountOptionLabel({ ...wire, is_primary: true }, words(wire))).toBe(
      "BE71 0961 2345 6769, Wire transfer (EUR, primary)",
    );
  });

  it("keep an identifier that is not an IBAN as it was typed", () => {
    const other = {
      ...account("3", "USD"),
      account_scheme: "other" as const,
      account_identifier: "026009593 1234567890",
      payment_means_code: "42" as const,
    };
    expect(
      payeeAccountOptionLabel(other, { means: "Bank transfer", primary: "primary" }),
    ).toBe("026009593 1234567890, Bank transfer (USD)");
  });

  it("each copy their own payment means and BIC when picked", () => {
    const [wire, sepa] = wireAndSepa();
    const picked = [wire, sepa].map((a) => toInvoicePayee(payeeFormFromAccount(a)));
    expect(picked.map((p) => [p.payment_means_code, p.bic])).toEqual([
      ["30", "REVOGB21"],
      ["58", "REVOLT21"],
    ]);
    expect(new Set(picked.map((p) => p.account_identifier))).toEqual(
      new Set(["BE71096123456769"]),
    );
  });

  it("are preselected by the lowest id when none is primary", () => {
    const [wire, sepa] = wireAndSepa();
    expect(preselectPayee([sepa, wire], "EUR")?.id).toBe("1");
  });

  it("are preselected by the primary flag when one is", () => {
    const [wire, sepa] = wireAndSepa();
    expect(preselectPayee([wire, { ...sepa, is_primary: true }], "EUR")?.id).toBe("2");
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
