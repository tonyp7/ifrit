import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { IssueInvoiceDialog } from "@/components/invoices/IssueInvoiceDialog";
import { VoidInvoiceDialog } from "@/components/invoices/VoidInvoiceDialog";
import { formatDueDate } from "@/lib/billingMilestones";
import type { IssuePreview } from "@/types/invoice";

// Radix renders a dialog through a portal, which server rendering leaves empty: render its
// parts inline so the body's markup (and every translation key it uses) is checked.
vi.mock("@/components/ui/alert-dialog", () => {
  const Inline = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  const Button = ({ children, disabled }: { children?: ReactNode; disabled?: boolean }) => (
    <button disabled={disabled}>{children}</button>
  );
  return {
    AlertDialog: Inline,
    AlertDialogContent: Inline,
    AlertDialogHeader: Inline,
    AlertDialogFooter: Inline,
    AlertDialogTitle: Inline,
    AlertDialogDescription: Inline,
    AlertDialogCancel: Button,
    AlertDialogAction: Button,
  };
});

const preview: IssuePreview = {
  invoice_date: "2026-10-14",
  due_date: "2026-11-13",
  payment_terms: "net_30",
  number: "INV-2026-0044",
  warnings: [{ code: "no_payee_account", service_lines: [], companies: [] }],
  blocking: [],
};

function renderIssue(overrides: Partial<IssuePreview> | null = {}) {
  return renderToStaticMarkup(
    <IssueInvoiceDialog
      open
      onOpenChange={vi.fn()}
      preview={overrides === null ? null : { ...preview, ...overrides }}
      minorUnit={2}
      issuing={false}
      onConfirm={vi.fn()}
    />,
  );
}

describe("IssueInvoiceDialog", () => {
  it("lists the dates, the preset, the likely number and the warnings", () => {
    const html = renderIssue();
    expect(html).toContain(formatDueDate("2026-10-14"));
    expect(html).toContain(`${formatDueDate("2026-11-13")} (Net 30)`);
    expect(html).toContain("INV-2026-0044");
    expect(html).toContain("No payee account");
    expect(html).toMatch(/<button>Issue<\/button>/);
  });

  it("warns about a due date before the invoice date without blocking", () => {
    const html = renderIssue({
      due_date: "2026-10-01",
      payment_terms: null,
      warnings: [{ code: "due_before_invoice_date", service_lines: [], companies: [] }],
    });
    expect(html).toContain("Due date before the invoice date");
    expect(html).toMatch(/<button>Issue<\/button>/);
  });

  it("disables Issue and says why when something blocks it", () => {
    const html = renderIssue({ blocking: ["project_not_active"] });
    expect(html).toContain("This invoice cannot be issued because its project is not Active.");
    expect(html).toMatch(/<button disabled="">Issue<\/button>/);
  });

  it("disables Issue while the preview loads", () => {
    expect(renderIssue(null)).toMatch(/<button disabled="">Issue<\/button>/);
  });
});

describe("VoidInvoiceDialog", () => {
  it("names the invoice and offers an optional reason", () => {
    const html = renderToStaticMarkup(
      <VoidInvoiceDialog
        open
        onOpenChange={vi.fn()}
        number="INV-2026-0043"
        voiding={false}
        onConfirm={vi.fn()}
      />,
    );
    expect(html).toContain("Void invoice INV-2026-0043?");
    expect(html).toContain("Reason (optional)");
    expect(html).toContain('maxLength="500"');
  });
});
