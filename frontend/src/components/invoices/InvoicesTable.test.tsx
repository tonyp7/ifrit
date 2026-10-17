import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import {
  InvoicesTable,
  InvoicesTableView,
  type InvoicesTableViewProps,
} from "@/components/invoices/InvoicesTable";
import { formatDueDate } from "@/lib/billingMilestones";
import { formatPeriod } from "@/lib/invoicePeriods";
import type { InvoiceListItem } from "@/types/invoice";

vi.mock("@/api/invoices", () => ({
  listInvoices: vi.fn(() => new Promise(() => {})),
  listInvoiceProjects: vi.fn(() => new Promise(() => {})),
  deleteInvoice: vi.fn(),
  duplicateInvoice: vi.fn(),
}));

const draft: InvoiceListItem = {
  id: "i1",
  status: "draft",
  project_id: "p1",
  project_name: "Website redesign",
  client_name: "ACME",
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  currency_code: "EUR",
  currency_minor_unit: 2,
  total: "19037.5000",
  payment_terms: "net_30",
  due_date: null,
  created_at: "2026-10-14T09:00:00Z",
  number: null,
  invoice_date: null,
  issued_at: null,
};

const issued: InvoiceListItem = {
  ...draft,
  id: "i2",
  status: "issued",
  number: "INV-2026-0043",
  invoice_date: "2026-10-14",
  issued_at: "2026-10-14T09:30:00Z",
  payment_terms: "net_30",
  due_date: "2026-11-13",
};

function render(items: InvoiceListItem[]) {
  const props: InvoicesTableViewProps = {
    items,
    sorting: [],
    onSortingChange: vi.fn(),
    pageCount: 1,
    onOpen: vi.fn(),
    onDuplicate: vi.fn(),
    onDelete: vi.fn(),
  };
  return renderToStaticMarkup(<InvoicesTableView {...props} />);
}

describe("InvoicesTableView", () => {
  it("shows the empty state", () => {
    expect(render([])).toContain("No invoices yet");
  });

  it("shows the columns in order", () => {
    const html = render([draft]);
    const headers = [
      "Number",
      "Project",
      "Client",
      "Billed for",
      "Status",
      "Total",
      "Created",
      "Issued",
      "Due",
    ];
    const positions = headers.map((header) => html.indexOf(`>${header}<`));
    expect(positions.every((position) => position > -1)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });

  it("shows a draft's preset due muted, the period and the total", () => {
    const html = render([draft]);
    expect(html).toContain("Website redesign");
    expect(html).toContain("ACME");
    // Dates follow the runner's locale, so the expected text comes from the same formatter.
    expect(html).toContain(formatPeriod(new Date(2026, 8, 1), new Date(2026, 8, 30)));
    expect(html).toContain("Draft");
    expect(html).toContain((19037.5).toLocaleString(undefined, { minimumFractionDigits: 2 }));
    expect(html).toMatch(/text-muted-foreground"[^>]*>Net 30</);
  });

  it("shows a fixed due date as a date", () => {
    const html = render([{ ...draft, payment_terms: null, due_date: "2026-12-01" }]);
    expect(html).toContain(formatDueDate("2026-12-01"));
    expect(html).not.toContain("Net 30");
  });
});

describe("issued rows", () => {
  it("shows the number, the invoice date and a real due date", () => {
    const html = render([issued]);
    expect(html).toContain("INV-2026-0043");
    expect(html).toContain("Issued");
    expect(html).toContain(formatDueDate("2026-10-14"));
    expect(html).toContain(formatDueDate("2026-11-13"));
    expect(html).not.toMatch(/text-muted-foreground"[^>]*>Net 30</);
  });
});

describe("InvoicesTable", () => {
  it("offers + New and the project filter", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <InvoicesTable />
      </MemoryRouter>,
    );
    expect(html).toContain("New");
    expect(html).toContain("Project");
    expect(html).toContain("Status");
  });
});
