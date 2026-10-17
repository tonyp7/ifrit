import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { InvoiceFormPage } from "@/pages/InvoiceFormPage";

// Requests never settle: the markup is what the page shows before anything has loaded.
vi.mock("@/api/invoices", () => ({
  listInvoiceProjects: vi.fn(() => new Promise(() => {})),
  getInvoice: vi.fn(() => new Promise(() => {})),
  getBillingContext: vi.fn(() => new Promise(() => {})),
  generateLines: vi.fn(),
  createInvoice: vi.fn(),
  updateInvoice: vi.fn(),
  deleteInvoice: vi.fn(),
}));

function render(path: string) {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/invoices/new" element={<InvoiceFormPage />} />
        <Route path="/invoices/:invoiceId" element={<InvoiceFormPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InvoiceFormPage", () => {
  it("titles a new invoice and starts with the project step only", () => {
    const html = render("/invoices/new");
    expect(html).toContain("New invoice");
    expect(html).toContain("Draft");
    expect(html).toContain("Choose a project…");
    expect(html).not.toContain("Line items");
    expect(html).toContain("Save draft");
    expect(html).toMatch(/>Issue</);
    expect(html).not.toContain("Delete draft");
    expect(html).not.toContain(">Void<");
  });

  it("titles a saved draft as an edit", () => {
    const html = render("/invoices/abc");
    expect(html).toContain("Edit invoice");
    expect(html).toContain("Delete draft");
  });
});
