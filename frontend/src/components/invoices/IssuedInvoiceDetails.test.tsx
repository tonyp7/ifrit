import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  InvoiceHeading,
  IssuedDates,
  IssuedIdentifiers,
  ProjectNotActiveBanner,
  VoidNotice,
} from "@/components/invoices/IssuedInvoiceDetails";
import { formatDueDate } from "@/lib/billingMilestones";
import type { InvoiceDetail, IssuePreview } from "@/types/invoice";

const issued = {
  status: "issued",
  number: "INV-2026-0043",
  document_name: "Tax Invoice",
  invoice_date: "2026-10-14",
  due_date: "2026-11-13",
  payment_terms: "net_30",
  voided_at: null,
  voided_by_name: null,
  void_reason: null,
} as unknown as InvoiceDetail;

const preview: IssuePreview = {
  invoice_date: "2026-10-17",
  due_date: null,
  payment_terms: null,
  number: "INV-2026-0044",
  warnings: [],
  blocking: [],
};

describe("InvoiceHeading", () => {
  it("titles an issued invoice by its document name and number", () => {
    const html = renderToStaticMarkup(
      <InvoiceHeading status="issued" detail={issued} preview={null} isNew={false} />,
    );
    expect(html).toContain("Tax Invoice");
    expect(html).toContain("INV-2026-0043");
    expect(html).toContain("Issued");
    expect(html).not.toContain("Edit invoice");
    expect(html).not.toContain("likely-number");
  });

  it("shows a saved draft's likely number", () => {
    const html = renderToStaticMarkup(
      <InvoiceHeading status="draft" detail={null} preview={preview} isNew={false} />,
    );
    expect(html).toContain("Edit invoice");
    expect(html).toContain("Likely number INV-2026-0044, assigned when issued");
  });

  it("says a new invoice gets its number when issued", () => {
    const html = renderToStaticMarkup(
      <InvoiceHeading status="draft" detail={null} preview={null} isNew />,
    );
    expect(html).toContain("New invoice");
    expect(html).toContain("Number assigned when issued");
  });
});

describe("ProjectNotActiveBanner", () => {
  it("shows only when the project blocks issuing", () => {
    const blocked = renderToStaticMarkup(
      <ProjectNotActiveBanner preview={{ ...preview, blocking: ["project_not_active"] }} />,
    );
    expect(blocked).toContain(
      "This invoice cannot be issued because its project is not Active.",
    );
    expect(renderToStaticMarkup(<ProjectNotActiveBanner preview={preview} />)).toBe("");
    expect(
      renderToStaticMarkup(
        <ProjectNotActiveBanner preview={{ ...preview, blocking: ["no_lines"] }} />,
      ),
    ).toBe("");
  });
});

describe("IssuedDates", () => {
  it("shows the due date with the preset in brackets", () => {
    const html = renderToStaticMarkup(<IssuedDates detail={issued} />);
    expect(html).toContain(formatDueDate("2026-10-14"));
    expect(html).toContain(`${formatDueDate("2026-11-13")} (Net 30)`);
  });

  it("shows a fixed due date alone", () => {
    const html = renderToStaticMarkup(
      <IssuedDates detail={{ ...issued, payment_terms: null, due_date: "2026-12-01" }} />,
    );
    expect(html).toContain(formatDueDate("2026-12-01"));
    expect(html).not.toContain("(");
  });
});

describe("VoidNotice", () => {
  it("says who voided it, when, and why", () => {
    const html = renderToStaticMarkup(
      <VoidNotice
        detail={{
          ...issued,
          status: "void",
          voided_at: "2026-10-15T10:00:00Z",
          voided_by_name: "Ada Lovelace",
          void_reason: "Wrong period",
        }}
      />,
    );
    expect(html).toContain("Voided by Ada Lovelace on");
    expect(html).toContain("Reason: Wrong period");
  });
});

describe("IssuedIdentifiers", () => {
  it("lists the frozen identifiers by their labels", () => {
    const html = renderToStaticMarkup(
      <IssuedIdentifiers
        title="Bill From identifiers"
        identifiers={[
          { id_type: "vat", scheme_id: null, id_value: "BE0123456789", is_primary: true },
          {
            id_type: "peppol_participant",
            scheme_id: "0208",
            id_value: "0123456789",
            is_primary: false,
          },
        ]}
      />,
    );
    expect(html).toContain("BE0123456789");
    expect(html).toContain("0208:0123456789");
    expect(renderToStaticMarkup(<IssuedIdentifiers title="X" identifiers={[]} />)).toContain(
      "No identifiers",
    );
  });
});
