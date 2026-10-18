import type { ReactNode } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { InvoiceLinesTable } from "@/components/invoices/InvoiceLinesTable";
import { InvoiceTaxesTable } from "@/components/invoices/InvoiceTaxesTable";
import { InvoiceReferencesFields } from "@/components/invoices/InvoiceReferencesFields";
import { InvoiceWarnings } from "@/components/invoices/InvoiceWarnings";
import { MilestoneBillingPanel } from "@/components/invoices/MilestoneBillingPanel";
import {
  BLANK_INVOICE_FORM,
  type InvoiceFormValues,
  type InvoiceLineFormValues,
  type InvoiceTaxFormValues,
} from "@/components/invoices/invoiceForm";
import { PartyFields } from "@/components/invoices/PartyFields";
import { PayeeAccountFields } from "@/components/invoices/PayeeAccountFields";
import { PaymentTermsField } from "@/components/invoices/PaymentTermsField";
import { TmBillingPanel } from "@/components/invoices/TmBillingPanel";
import { formatDueDate } from "@/lib/billingMilestones";
import { BLANK_PAYEE_ACCOUNT_VALUES } from "@/lib/payeeAccounts";
import { formatMoney } from "@/lib/format";
import type { ContextAddress, ContextCompany, ContextMilestone } from "@/types/invoice";

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

describe("MilestoneBillingPanel", () => {
  const milestones: ContextMilestone[] = [
    { id: "m1", description: "Phase 1", due_date: "2026-11-01", value: "10000.0000" },
    { id: "m2", description: "Phase 2", due_date: null, value: "12000.0000" },
  ];

  function render(list: ContextMilestone[], selected: string[]) {
    return renderToStaticMarkup(
      <MilestoneBillingPanel
        milestones={list}
        selected={selected}
        onSelectedChange={vi.fn()}
        currencyCode="EUR"
        minorUnit={2}
      />,
    );
  }

  it("lists every milestone in order with its value, none ticked", () => {
    const html = render(milestones, []);
    const first = html.indexOf("Phase 1");
    expect(first).toBeGreaterThan(-1);
    expect(html.indexOf("Phase 2")).toBeGreaterThan(first);
    expect(html).toContain(`${formatMoney("10000", 2)} EUR`);
    expect(html).toContain(`${formatMoney("12000", 2)} EUR`);
    expect(html).toContain(`Due ${formatDueDate("2026-11-01")}`);
    expect(html).not.toContain('aria-checked="true"');
    expect(html).not.toContain("Period");
  });

  it("ticks several milestones", () => {
    const html = render(
      [...milestones, { id: "m3", description: "Phase 3", due_date: null, value: "5000" }],
      ["m3", "m1"],
    );
    const checked = (id: string) =>
      new RegExp(`role="checkbox" aria-checked="(true|false)"[^>]*id="milestone_${id}"`).exec(
        html,
      )?.[1];
    expect([checked("m1"), checked("m2"), checked("m3")]).toEqual(["true", "false", "true"]);
  });

  it("says milestones must be added first when there are none", () => {
    const html = render([], []);
    expect(html).toContain("A manager must add them on the project first.");
    expect(html).not.toContain('role="checkbox"');
  });
});

describe("InvoiceTaxesTable", () => {
  // Lines adding up to 19,037.50, the worked example's subtotal.
  const exampleLines: InvoiceLineFormValues[] = [
    { key: "l1", description: "Dev", quantity: "152.5", uom: "hours", unit_price: "95" },
    { key: "l2", description: "Arch", quantity: "40", uom: "hours", unit_price: "120" },
    { key: "l3", description: "Discount", quantity: "1", uom: "ea", unit_price: "-250" },
  ];
  function tax(key: string, values: Partial<InvoiceTaxFormValues>): InvoiceTaxFormValues {
    return {
      key,
      label: key,
      base_mode: "subtotal",
      rate: "",
      amount: "",
      amount_set_by_hand: false,
      ...values,
    };
  }
  const example = [
    tax("GST", { rate: "5" }),
    tax("QST", { base_mode: "cumulative", rate: "9.975" }),
    tax("Eco levy", { amount: "100.00", amount_set_by_hand: true }),
  ];
  const render = (values: Partial<InvoiceFormValues>) =>
    withForm(values, (form) => (
      <InvoiceTaxesTable form={form} currencyCode="EUR" minorUnit={2} />
    ));

  it("computes the worked example, with Subtotal as text on the first row", () => {
    const html = render({ lines: exampleLines, taxes: example });
    expect(html).toContain(`on ${formatMoney("19037.50", 2)}`);
    expect(html).toContain(`on ${formatMoney("19989.38", 2)}`);
    expect(html).toContain('value="951.88"');
    expect(html).toContain('value="1993.94"');
    expect(html).toContain(`Total (EUR)`);
    expect(html).toContain(formatMoney("22083.32", 2));
    // One Applies to dropdown each for the second and third rows, plain text on the first.
    expect(html.match(/aria-label="Applies to"/g)).toHaveLength(2);
    expect(html).toMatch(/<p class="[^"]*">Subtotal<\/p>/);
    expect(html.match(/aria-label="Drag to reorder /g)).toHaveLength(3);
  });

  it("marks a hand-set amount and shows the rate it works out to", () => {
    const html = render({ lines: exampleLines, taxes: example });
    expect(html).toContain("≈ 0.525 %");
    expect(html).toContain("Set by hand");
    expect(html).toContain('aria-label="Calculate from the rate again"');
  });

  it("shows — for a hand-set amount on a zero base", () => {
    const html = render({
      lines: [],
      taxes: [tax("Levy", { amount: "10.00", amount_set_by_hand: true })],
    });
    expect(html).toMatch(/data-testid="derived-rate"[^>]*>—</);
    expect(html).not.toContain("Drag to reorder");
  });

  it("shows the stored rows read-only on an issued invoice", () => {
    const html = withForm({ lines: exampleLines, taxes: example }, (form) => (
      <InvoiceTaxesTable
        form={form}
        currencyCode="EUR"
        minorUnit={2}
        disabled
        stored={{
          total: "22083.3200",
          taxes: [
            {
              label: "GST",
              base_mode: "subtotal",
              rate: "5.000",
              amount: "951.8800",
              amount_set_by_hand: false,
              base_amount: "19037.5000",
            },
            {
              label: "Eco levy",
              base_mode: "subtotal",
              rate: "0.525",
              amount: "100.0000",
              amount_set_by_hand: true,
              base_amount: "19037.5000",
            },
          ],
        }}
      />
    ));
    expect(html).toContain("5 %");
    expect(html).toContain("≈ 0.525 %");
    expect(html).toContain(formatMoney("22083.32", 2));
    expect(html).not.toContain("<input");
    expect(html).not.toContain("Add tax");
    expect(html).not.toContain("Drag to reorder");
    expect(html).not.toContain("Delete tax");
  });

  it("offers + Add tax and the total with no rows", () => {
    const html = render({ lines: exampleLines, taxes: [] });
    expect(html).toContain("Add tax");
    expect(html).toContain(formatMoney("19037.50", 2));
    expect(html).not.toContain("<table");
  });
});
