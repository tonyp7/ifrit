import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { AddressesTable } from "@/components/companies/AddressesTable";
import { CompanyNameCell } from "@/components/companies/CompaniesTable";
import { PartyIdentifiersTable } from "@/components/companies/PartyIdentifiersTable";
import { PayeeAccountsTable } from "@/components/companies/PayeeAccountsTable";
import {
  InvoicesTableView,
  type InvoicesTableViewProps,
} from "@/components/invoices/InvoicesTable";
import { BillingMilestonesSectionView } from "@/components/projects/BillingMilestonesSectionView";
import { ProjectNameCell } from "@/components/projects/ProjectsTable";
import { ProjectReferencesSectionView } from "@/components/projects/ProjectReferencesSectionView";
import { ServiceLinesTable } from "@/components/projects/ServiceLinesTable";
import { UserNameCell } from "@/components/users/UsersTable";
import type { Address, PartyIdentifier, PayeeAccount } from "@/types/company";
import type { InvoiceListItem } from "@/types/invoice";
import type { BillingMilestone, ProjectReference, ServiceLine } from "@/types/project";

// Radix renders a menu's content only when it is open, which server rendering never is: render
// the menu inline so its items, their order and the separator can be read.
vi.mock("@/components/ui/dropdown-menu", () => {
  const Inline = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    DropdownMenu: Inline,
    DropdownMenuTrigger: Inline,
    DropdownMenuContent: Inline,
    DropdownMenuCheckboxItem: Inline,
    DropdownMenuItem: ({
      children,
      className,
    }: {
      children?: ReactNode;
      className?: string;
    }) => (
      <div role="menuitem" className={className}>
        {children}
      </div>
    ),
    DropdownMenuSeparator: () => <hr role="separator" />,
  };
});

// Rendered with the global English i18n instance (src/test/setup.ts), which fails the test
// on any key missing from public/locales/en.
const noop = vi.fn();

/** The position of each marker in the markup, in the order given, or the first one missing. */
function inOrder(html: string, ...markers: string[]): boolean {
  let at = -1;
  for (const marker of markers) {
    const next = html.indexOf(marker, at + 1);
    if (next === -1) return false;
    at = next;
  }
  return true;
}

function expectMenuOrder(html: string) {
  // Edit, Duplicate, a separator, then the destructive Delete.
  expect(inOrder(html, ">Edit<", ">Duplicate<", 'role="separator"', ">Delete<")).toBe(true);
  expect(html).toMatch(/role="menuitem" class="[^"]*text-destructive[^"]*">Delete</);
}

describe("the primary cell of each list opens the row's page", () => {
  function render(node: ReactNode) {
    return renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);
  }

  it("projects: the name", () => {
    const html = render(<ProjectNameCell id="p1" name="Website redesign" />);
    expect(html).toContain('href="/projects/p1"');
    expect(html).toContain(">Website redesign</a>");
  });

  it("users: the full name", () => {
    const html = render(<UserNameCell id="u1" fullName="Ada Lovelace" />);
    expect(html).toContain('href="/configuration/users/u1"');
    expect(html).toContain(">Ada Lovelace</a>");
  });

  it("companies: the legal name", () => {
    const html = render(<CompanyNameCell id="c1" legalName="ACME Ltd" />);
    expect(html).toContain('href="/configuration/companies/c1"');
    expect(html).toContain(">ACME Ltd</a>");
  });
});

describe("the invoices list", () => {
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
    total: "100.0000",
    payment_terms: "net_30",
    due_date: null,
    created_at: "2026-10-14T09:00:00Z",
    number: null,
    invoice_date: null,
    issued_at: null,
    lines_summary: "Work",
    has_pdf: false,
  };
  const issued: InvoiceListItem = {
    ...draft,
    id: "i2",
    status: "issued",
    number: "INV-2026-0043",
    invoice_date: "2026-10-14",
    issued_at: "2026-10-14T09:30:00Z",
    has_pdf: true,
  };
  const voided: InvoiceListItem = { ...issued, id: "i3", status: "void" };

  function render(items: InvoiceListItem[]) {
    const props: InvoicesTableViewProps = {
      items,
      pageCount: 1,
      sorting: [],
      columnVisibility: { issued: false, due: false },
      onSortingChange: noop,
      onColumnVisibilityChange: noop,
      onOpen: noop,
      onDuplicate: noop,
      onDownload: noop,
      onDelete: noop,
    };
    return renderToStaticMarkup(
      <MemoryRouter>
        <InvoicesTableView {...props} />
      </MemoryRouter>,
    );
  }

  it("opens an issued invoice from its number, named by it", () => {
    const html = render([issued]);
    expect(html).toContain('href="/invoices/i2"');
    expect(html).toContain(">INV-2026-0043</a>");
  });

  it("keeps a draft's number cell empty and gives its link a name", () => {
    const html = render([draft]);
    expect(html).toContain('href="/invoices/i1"');
    expect(html).toContain('aria-label="Edit invoice for Website redesign"');
    expect(html).not.toContain("Draft</a>");
  });

  it("says Edit on a draft and View on an issued or void invoice", () => {
    const draftHtml = render([draft]);
    expect(draftHtml).toContain(">Edit<");
    expect(draftHtml).not.toContain(">View<");
    expect(draftHtml).not.toContain(">Open<");
    for (const invoice of [issued, voided]) {
      const html = render([invoice]);
      expect(html).toContain(">View<");
      expect(html).not.toContain(">Edit<");
    }
  });

  it("separates Delete from the other items on a draft", () => {
    const html = render([draft]);
    expect(inOrder(html, ">Edit<", ">Duplicate<", 'role="separator"', ">Delete<")).toBe(true);
  });
});

describe("the tables inside the project form", () => {
  const line: ServiceLine = {
    id: "l1",
    project_id: "p",
    name: "Senior developer",
    quantity: "10",
    uom: "days",
    unit_price: "500",
    value: "5000",
    is_active: true,
    users: [],
  };
  const reference: ProjectReference = {
    id: "r1",
    project_id: "p",
    kind: "purchase_order",
    label: null,
    value: "PO-1",
    position: 0,
  };
  const milestone: BillingMilestone = {
    id: "m1",
    project_id: "p",
    description: "Kick-off",
    due_date: "2026-11-01",
    value: "1000",
    position: 0,
  };

  function serviceLines(lines: ServiceLine[], readOnly = false) {
    return renderToStaticMarkup(
      <ServiceLinesTable
        projectId="p"
        serviceLines={lines}
        onChanged={noop}
        ensureSaved={vi.fn()}
        readOnly={readOnly}
        minorUnit={2}
      />,
    );
  }

  function references(readOnly = false) {
    return renderToStaticMarkup(
      <ProjectReferencesSectionView
        references={[reference]}
        readOnly={readOnly}
        error={null}
        onAdd={noop}
        onEdit={noop}
        onDuplicate={noop}
        onDeleteRequest={noop}
        onReorder={noop}
      />,
    );
  }

  function milestones(readOnly = false) {
    return renderToStaticMarkup(
      <BillingMilestonesSectionView
        milestones={[milestone]}
        contractValue="5000"
        minorUnit={2}
        readOnly={readOnly}
        error={null}
        onAdd={noop}
        onEdit={noop}
        onDuplicate={noop}
        onDeleteRequest={noop}
        onReorder={noop}
      />,
    );
  }

  it("service lines: the name opens the dialog; the menu separates Delete", () => {
    const html = serviceLines([line]);
    expect(html).toMatch(/<button type="button"[^>]*>Senior developer<\/button>/);
    expectMenuOrder(html);
  });

  it("service lines: an empty name keeps its dash and is named for assistive technology", () => {
    const html = serviceLines([{ ...line, name: null }]);
    expect(html).toMatch(
      /<button type="button"[^>]*aria-label="Edit service line"[^>]*>—<\/button>/,
    );
  });

  it("service lines: read-only shows plain text", () => {
    const html = serviceLines([line], true);
    expect(html).toContain("Senior developer");
    expect(html).not.toContain(">Senior developer</button>");
  });

  it("references: the reference name opens the dialog; the menu separates Delete", () => {
    const html = references();
    expect(html).toMatch(/<button type="button"[^>]*>Purchase order<\/button>/);
    expectMenuOrder(html);
  });

  it("references: read-only shows plain text", () => {
    const html = references(true);
    expect(html).toContain("Purchase order");
    expect(html).not.toContain('<button type="button"');
  });

  it("milestones: the description opens the dialog; the menu separates Delete", () => {
    const html = milestones();
    expect(html).toMatch(/<button type="button"[^>]*>Kick-off<\/button>/);
    expectMenuOrder(html);
  });

  it("milestones: read-only shows plain text", () => {
    const html = milestones(true);
    expect(html).toContain("Kick-off");
    expect(html).not.toContain(">Kick-off</button>");
  });
});

describe("the tables inside the company form", () => {
  const identifier: PartyIdentifier = {
    id: "i1",
    company_id: "c",
    id_type: "vat",
    scheme_id: null,
    id_value: "BE0123456749",
    is_primary: true,
    valid_from: null,
    valid_to: null,
  };
  const address: Address = {
    id: "a1",
    company_id: "c",
    address_type: "registered",
    line1: "Rue de la Loi 1",
    line2: null,
    line3: null,
    city: "Brussels",
    postal_zone: "1000",
    country_subdivision: null,
    country_code: "BE",
    is_primary: true,
    valid_from: null,
    valid_to: null,
  };
  const account: PayeeAccount = {
    id: "p1",
    company_id: "c",
    payment_means_code: "30",
    account_scheme: "iban",
    account_identifier: "BE71096123456769",
    account_name: null,
    currency_code: "EUR",
    bic: null,
    bank_name: null,
    bank_address: null,
    is_primary: true,
  };

  it("identifiers: the type opens the dialog; the menu separates Delete", () => {
    const html = renderToStaticMarkup(
      <PartyIdentifiersTable
        companyId="c"
        identifiers={[identifier]}
        onChanged={noop}
        ensureSaved={vi.fn()}
      />,
    );
    expect(html).toMatch(/<button type="button"[^>]*>VAT<\/button>/);
    expectMenuOrder(html);
  });

  it("addresses: the type opens the dialog; the menu separates Delete", () => {
    const html = renderToStaticMarkup(
      <AddressesTable
        companyId="c"
        addresses={[address]}
        onChanged={noop}
        ensureSaved={vi.fn()}
      />,
    );
    expect(html).toMatch(/<button type="button"[^>]*>Registered<\/button>/);
    expectMenuOrder(html);
  });

  it("payee accounts: the payment means opens the dialog; the menu separates Delete", () => {
    const html = renderToStaticMarkup(
      <PayeeAccountsTable
        companyId="c"
        accounts={[account]}
        onChanged={noop}
        ensureSaved={vi.fn()}
      />,
    );
    expect(html).toMatch(/<button type="button"[^>]*>Wire transfer<\/button>/);
    expectMenuOrder(html);
  });
});
