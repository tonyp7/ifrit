import type { ReactNode } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { InvoiceLinesTable } from "@/components/invoices/InvoiceLinesTable";
import { InvoiceReferencesFields } from "@/components/invoices/InvoiceReferencesFields";
import { InvoiceWarnings } from "@/components/invoices/InvoiceWarnings";
import {
  BLANK_INVOICE_FORM,
  type InvoiceFormValues,
  type InvoiceLineFormValues,
} from "@/components/invoices/invoiceForm";
import { PartyFields } from "@/components/invoices/PartyFields";
import { PayeeAccountFields } from "@/components/invoices/PayeeAccountFields";
import { PaymentTermsField } from "@/components/invoices/PaymentTermsField";
import { TmBillingPanel } from "@/components/invoices/TmBillingPanel";
import { formatDueDate } from "@/lib/billingMilestones";
import { BLANK_PAYEE_ACCOUNT_VALUES } from "@/lib/payeeAccounts";
import type { ContextAddress, ContextCompany } from "@/types/invoice";

vi.mock("@/api/currencies", () => ({ listCurrencies: vi.fn(() => new Promise(() => {})) }));

// Renders a section bound to a real form holding `values`.
function withForm(
  values: Partial<InvoiceFormValues>,
  render: (form: UseFormReturn<InvoiceFormValues>) => ReactNode,
) {
  function Harness() {
    const form = useForm<InvoiceFormValues>({
      defaultValues: { ...BLANK_INVOICE_FORM, ...values },
    });
    return <>{render(form)}</>;
  }
  return renderToStaticMarkup(<Harness />);
}

function address(id: string): ContextAddress {
  return {
    id,
    address_type: "registered",
    is_primary: false,
    line1: `${id} Main Street`,
    line2: null,
    line3: null,
    city: "London",
    postal_zone: null,
    country_subdivision: null,
    country_code: "GB",
  };
}

const company = (addresses: ContextAddress[]): ContextCompany => ({
  id: "c",
  display_name: "ACME",
  is_active: true,
  addresses,
});

function line(description: string): InvoiceLineFormValues {
  return { key: description, description, quantity: "2", uom: "hours", unit_price: "95" };
}

describe("PartyFields", () => {
  it("offers an address dropdown only when the company has more than one", () => {
    const two = withForm({}, (form) => (
      <PartyFields
        side="bill_to"
        title="Bill To"
        company={company([address("1"), address("2")])}
        form={form}
      />
    ));
    const one = withForm({}, (form) => (
      <PartyFields
        side="bill_to"
        title="Bill To"
        company={company([address("1")])}
        form={form}
      />
    ));
    expect(two).toContain("Copy one of the company");
    expect(one).not.toContain("Copy one of the company");
    expect(one).toContain('id="bill_to_name"');
  });
});

describe("PayeeAccountFields", () => {
  it("says there is no payee account when none is filled in", () => {
    const html = withForm({ payee: null }, (form) => (
      <PayeeAccountFields accounts={[]} invoiceCurrency="EUR" form={form} />
    ));
    expect(html).toContain("No payee account on this invoice.");
    expect(html).toContain("The vendor has no payee account");
  });

  it("shows the copied details as editable fields", () => {
    const html = withForm(
      {
        payee: {
          ...BLANK_PAYEE_ACCOUNT_VALUES,
          account_identifier: "BE71 0961 2345 6769",
          currency_code: "EUR",
        },
      },
      (form) => <PayeeAccountFields accounts={[]} invoiceCurrency="EUR" form={form} />,
    );
    // Registered inputs get their value once mounted, so the markup shows the fields only.
    expect(html).toContain('id="payee_account_identifier"');
    expect(html).toContain('id="payee_bic"');
    expect(html).not.toContain("No payee account on this invoice.");
    expect(html).toContain("Clear payee account");
  });
});

describe("PaymentTermsField", () => {
  const today = new Date(2026, 9, 14);

  it("estimates the due date of a preset from today", () => {
    const html = renderToStaticMarkup(
      <PaymentTermsField
        paymentTerms="net_30"
        dueDate={null}
        onChange={vi.fn()}
        today={today}
      />,
    );
    expect(html).toContain("Calculated when the invoice is issued. If issued today:");
    expect(html).toContain(formatDueDate("2026-11-13"));
  });

  it("labels a hand-picked date as fixed", () => {
    const html = renderToStaticMarkup(
      <PaymentTermsField
        paymentTerms={null}
        dueDate="2026-12-01"
        onChange={vi.fn()}
        today={today}
      />,
    );
    expect(html).toContain("Fixed date");
    expect(html).not.toContain("If issued today");
  });
});

describe("InvoiceReferencesFields", () => {
  it("asks which value for a kind the project has several of", () => {
    const html = withForm(
      {
        references: [
          { kind: "purchase_order", label: "", value: "", options: ["PO-1", "PO-2"] },
        ],
      },
      (form) => <InvoiceReferencesFields form={form} />,
    );
    expect(html).toContain("Which one is this invoice for?");
    expect(html).toContain("Add reference");
  });

  it("says when there are none", () => {
    const html = withForm({ references: [] }, (form) => (
      <InvoiceReferencesFields form={form} />
    ));
    expect(html).toContain("No references on this invoice.");
  });
});

describe("TmBillingPanel", () => {
  it("names an unnamed service line by its unit and price, and marks the preset", () => {
    const html = renderToStaticMarkup(
      <TmBillingPanel
        serviceLines={[{ id: "s1", name: null, uom: "days", unit_price: "700" }]}
        selected={["s1"]}
        onSelectedChange={vi.fn()}
        period={{ preset: "last_month", start: "2026-09-01", end: "2026-09-30" }}
        onPeriodChange={vi.fn()}
        minorUnit={2}
        today={new Date(2026, 9, 14)}
      />,
    );
    expect(html).toContain("Days at 700.00");
    expect(html).toMatch(/aria-pressed="true"[^>]*>Last month</);
    expect(html).toMatch(/aria-pressed="false"[^>]*>This month</);
  });
});

describe("InvoiceLinesTable", () => {
  it("shows no grip for a single line", () => {
    const html = withForm({ lines: [line("Work")] }, (form) => (
      <InvoiceLinesTable form={form} currencyCode="EUR" minorUnit={2} />
    ));
    expect(html).not.toContain("Drag to reorder");
    expect(html).toContain("190.00 EUR");
  });

  it("shows a grip per line when there are several", () => {
    const html = withForm({ lines: [line("Work"), line("Fee")] }, (form) => (
      <InvoiceLinesTable form={form} currencyCode="EUR" minorUnit={2} />
    ));
    expect(html.match(/aria-label="Drag to reorder /g)).toHaveLength(2);
    expect(html).toContain("380.00 EUR");
  });

  it("gives the table a minimum width inside the table's scroll wrapper", () => {
    const html = withForm({ lines: [] }, (form) => (
      <InvoiceLinesTable form={form} currencyCode="EUR" minorUnit={2} />
    ));
    expect(html).toMatch(/overflow-auto"><table class="[^"]*min-w-\[44rem\]/);
    expect(html).toContain("No lines yet. Generate them or add one.");
  });
});

describe("InvoiceWarnings", () => {
  it("renders each warning and the lines left out", () => {
    const html = renderToStaticMarkup(
      <InvoiceWarnings
        minorUnit={2}
        omitted={[{ service_line_id: "s", name: "Idle", uom: "hours", unit_price: "95" }]}
        warnings={[
          {
            code: "unlocked_hours",
            companies: [],
            service_lines: [
              { name: "Senior developer", uom: "hours", unit_price: "95", days: 3 },
            ],
          },
          { code: "payee_currency", service_lines: [], companies: [] },
          { code: "inactive_company", service_lines: [], companies: ["client"] },
        ]}
      />,
    );
    expect(html).toContain("Senior developer (3 days)");
    expect(html).toContain("Payee account currency");
    expect(html).toContain("client has been deactivated");
    expect(html).toContain("left out: Idle");
  });

  it("renders nothing when there is nothing to say", () => {
    expect(
      renderToStaticMarkup(<InvoiceWarnings minorUnit={2} omitted={[]} warnings={[]} />),
    ).toBe("");
  });
});
