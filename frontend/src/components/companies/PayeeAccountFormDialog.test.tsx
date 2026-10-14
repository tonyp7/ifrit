import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { PayeeAccountFormDialog } from "@/components/companies/PayeeAccountFormDialog";
import { BLANK_ADDRESS_FIELDS, BLANK_PAYEE_ACCOUNT_VALUES } from "@/lib/payeeAccounts";

// Radix renders a dialog through a portal, which server rendering leaves empty: render its
// parts inline so the body's markup (and every translation key it uses) is checked.
vi.mock("@/components/ui/dialog", () => {
  const Inline = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    Dialog: Inline,
    DialogContent: Inline,
    DialogFooter: Inline,
    DialogHeader: Inline,
    DialogTitle: Inline,
  };
});

// Rendered with the global English i18n instance (src/test/setup.ts), which fails the test
// on any key missing from public/locales/en.
function render(props: Partial<Parameters<typeof PayeeAccountFormDialog>[0]> = {}) {
  return renderToStaticMarkup(
    <PayeeAccountFormDialog
      open
      onOpenChange={vi.fn()}
      companyId="c"
      onSaved={vi.fn()}
      {...props}
    />,
  );
}

describe("PayeeAccountFormDialog", () => {
  it("renders the add form with its fields and the bank address block", () => {
    const html = render();
    expect(html).toContain("Add payee account");
    expect(html).toContain("Payment means");
    expect(html).toContain("IBAN");
    expect(html).toContain("Account name");
    expect(html).toContain("Currency");
    expect(html).toContain("BIC");
    expect(html).toContain("Bank name");
    expect(html).toContain("Bank address");
    expect(html).toContain('id="bank_line1"');
    expect(html).toContain('id="bank_country_code"');
    // The bank country is the country picker, still empty.
    expect(html).toMatch(/id="bank_country_code"[^>]*role="combobox"/);
    expect(html).toContain("Select a country…");
    expect(html).toContain("Primary for this currency");
  });

  it("titles an edit and labels a national account number", () => {
    const html = render({
      accountId: "a",
      initialValues: {
        ...BLANK_PAYEE_ACCOUNT_VALUES,
        payment_means_code: "30",
        account_scheme: "other",
        account_identifier: "123-456789-0",
        bank_address: BLANK_ADDRESS_FIELDS,
      },
    });
    expect(html).toContain("Edit payee account");
    expect(html).toContain("Account number");
  });
});
