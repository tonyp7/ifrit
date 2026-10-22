import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { PayeeAccountsTable } from "@/components/companies/PayeeAccountsTable";
import type { PayeeAccount } from "@/types/company";

function account(overrides: Partial<PayeeAccount> = {}): PayeeAccount {
  return {
    id: "a",
    company_id: "c",
    payment_means_code: "58",
    account_scheme: "iban",
    account_identifier: "BE71096123456769",
    account_name: null,
    currency_code: "EUR",
    bic: "GEBABEBB",
    bank_name: null,
    bank_address: null,
    is_primary: true,
    ...overrides,
  };
}

// Rendered with the global English i18n instance (src/test/setup.ts), which fails the test
// on any key missing from public/locales/en.
function render(accounts: PayeeAccount[]) {
  return renderToStaticMarkup(
    <PayeeAccountsTable
      companyId="c"
      accounts={accounts}
      onChanged={vi.fn()}
      ensureSaved={vi.fn()}
    />,
  );
}

describe("PayeeAccountsTable", () => {
  it("shows the empty state", () => {
    const html = render([]);
    expect(html).toContain("Payee Accounts");
    expect(html).toContain("No payee accounts yet.");
  });

  it("shows labels, never raw codes, and an IBAN grouped in fours", () => {
    const html = render([
      account(),
      account({
        id: "b",
        payment_means_code: "30",
        account_scheme: "other",
        account_identifier: "026009593 1234567890",
        currency_code: "USD",
        bic: null,
        bank_name: "Bank of America",
        is_primary: false,
      }),
      account({
        id: "c",
        payment_means_code: "42",
        account_identifier: "NL91ABNA0417164300",
        bic: null,
      }),
    ]);
    expect(html).toContain("SEPA credit transfer");
    expect(html).toContain("Wire transfer");
    expect(html).toContain("Bank transfer");
    expect(html).not.toContain("Credit transfer");
    expect(html).not.toContain("Payment to bank account");
    expect(html).toContain("BE71 0961 2345 6769");
    expect(html).toContain("026009593 1234567890");
    // Bank: the bank's name, else its BIC, else a dash.
    expect(html).toContain("Bank of America");
    expect(html).toContain("GEBABEBB");
    expect(html).toContain("—");
    expect(html).not.toContain(">58<");
  });
});
