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
  lines_summary: "Senior developer — September 2026",
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

// What the list starts with: Issued and Due are optional and hidden.
const DEFAULT_VISIBILITY = { issued: false, due: false };
const ALL_VISIBLE = { issued: true, due: true };

function render(items: InvoiceListItem[], columnVisibility = DEFAULT_VISIBILITY) {
  const props: InvoicesTableViewProps = {
    items,
    sorting: [],
    onSortingChange: vi.fn(),
    pageCount: 1,
    columnVisibility,
    onColumnVisibilityChange: vi.fn(),
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

  it("shows the default columns in order, without Issued and Due", () => {
    const html = render([draft]);
    const headers = [
      "Number",
      "Status",
      "Project",
      "Client",
      "Billed for",
      "Created",
      "Total",
    ];
    const positions = headers.map((header) => html.indexOf(`>${header}<`));
    expect(positions.every((position) => position > -1)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    expect(html).not.toContain(">Issued<");
    expect(html).not.toContain(">Due<");
  });

  it("shows Issued and Due after Total when they are switched on", () => {
    const html = render([draft], ALL_VISIBLE);
    const headers = ["Total", "Issued", "Due"];
    const positions = headers.map((header) => html.indexOf(`>${header}<`));
    expect(positions.every((position) => position > -1)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });

  it("hides one of them again without moving the others", () => {
    const html = render([draft], { issued: true, due: false });
    expect(html).toContain(">Issued<");
    expect(html).not.toContain(">Due<");
    expect(html.indexOf(">Total<")).toBeLessThan(html.indexOf(">Issued<"));
  });

  it("spans the empty state over the visible columns only", () => {
    // Seven data columns and the row menu by default, two more when both are shown.
    expect(render([])).toContain('colSpan="8"');
    expect(render([], ALL_VISIBLE)).toContain('colSpan="10"');
  });

  it("shows a draft's preset due muted, the period and the total", () => {
    const html = render([draft], ALL_VISIBLE);
    expect(html).toContain("Website redesign");
    expect(html).toContain("ACME");
    // Dates follow the runner's locale, so the expected text comes from the same formatter.
    expect(html).toContain(formatPeriod(new Date(2026, 8, 1), new Date(2026, 8, 30)));
    expect(html).toContain("Draft");
    expect(html).toContain((19037.5).toLocaleString(undefined, { minimumFractionDigits: 2 }));
    expect(html).toMatch(/text-muted-foreground"[^>]*>Net 30</);
  });

  it("shows every line, clipped, when there is no period", () => {
    const fixedPrice = {
      ...draft,
      period_start: null,
      period_end: null,
      lines_summary: "Downpayment, End of SIT",
    };
    const empty = { ...fixedPrice, id: "i3", lines_summary: null };
    const html = render([fixedPrice, empty]);
    expect(html).toMatch(/<span class="[^"]*truncate[^"]*">Downpayment, End of SIT<\/span>/);
    expect(html).not.toContain('title="Downpayment');
    expect(html).not.toContain("Senior developer — September 2026");
    expect(html).toContain("—");
  });

  it("shows a fixed due date as a date", () => {
    const html = render(
      [{ ...draft, payment_terms: null, due_date: "2026-12-01" }],
      ALL_VISIBLE,
    );
    expect(html).toContain(formatDueDate("2026-12-01"));
    expect(html).not.toContain("Net 30");
  });
});

describe("issued rows", () => {
  it("shows the number, the invoice date and a real due date", () => {
    const html = render([issued], ALL_VISIBLE);
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

  it("puts the search box first, before the filters, and full width on a phone", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <InvoicesTable />
      </MemoryRouter>,
    );
    const search = html.indexOf('placeholder="Search invoices…"');
    expect(search).toBeGreaterThan(-1);
    expect(search).toBeLessThan(html.indexOf("Status"));
    expect(search).toBeLessThan(html.indexOf("Project"));
    expect(html).toContain("w-full sm:w-96");
  });

  it("puts the Columns button right before + New, with the optional columns hidden", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <InvoicesTable />
      </MemoryRouter>,
    );
    const columns = html.indexOf("Columns");
    expect(columns).toBeGreaterThan(-1);
    expect(columns).toBeLessThan(html.indexOf("New"));
    // Between the two labels there is only the end of the Columns button and the start of New.
    expect(html.slice(columns, html.indexOf("New")).match(/<button/g)).toHaveLength(1);
    expect(html.indexOf("Project")).toBeLessThan(columns);
    expect(html.indexOf("Status")).toBeLessThan(columns);
    expect(html).not.toContain(">Issued<");
    expect(html).not.toContain(">Due<");
  });
});
