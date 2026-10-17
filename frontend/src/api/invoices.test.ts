import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import {
  createInvoice,
  deleteInvoice,
  duplicateInvoice,
  generateLines,
  getBillingContext,
  getInvoice,
  listInvoiceProjects,
  listInvoices,
  updateInvoice,
} from "@/api/invoices";
import type { InvoiceInput } from "@/types/invoice";

vi.mock("@/api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

const input: InvoiceInput = {
  project_id: "p1",
  bill_from: { name: "Ifrit", address: null },
  bill_to: { name: "ACME", address: null },
  period_start: "2026-09-01",
  period_end: "2026-09-30",
  payment_terms: "net_30",
  due_date: null,
  payee: null,
  references: [],
  lines: [],
};

describe("invoice API", () => {
  it("lists invoices with paging, sorting and the project filter", () => {
    void listInvoices({ page: 2, sort_by: "total", sort_dir: "desc", projectId: "p1" });
    void listInvoices({});
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      "/invoices?page=2&sort_by=total&sort_dir=desc&project_id=p1",
    );
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/invoices?page=1");
  });

  it("lists invoiceable projects, or the invoiced ones for the filter", () => {
    void listInvoiceProjects();
    void listInvoiceProjects({ search: "web", invoiced: true });
    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/invoices/projects");
    expect(apiClient.get).toHaveBeenNthCalledWith(
      2,
      "/invoices/projects?search=web&invoiced=true",
    );
  });

  it("reads a project's billing context and generates lines", () => {
    void getBillingContext("p1");
    const generate = {
      project_id: "p1",
      service_line_ids: ["s1"],
      period_start: "2026-09-01",
      period_end: "2026-09-30",
    };
    void generateLines(generate);
    expect(apiClient.get).toHaveBeenCalledWith("/invoices/projects/p1");
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/generate", generate);
  });

  it("creates, reads, updates, duplicates and deletes", () => {
    void createInvoice(input);
    void getInvoice("i1");
    void updateInvoice("i1", input);
    void duplicateInvoice("i1");
    void deleteInvoice("i1");
    expect(apiClient.post).toHaveBeenCalledWith("/invoices", input);
    expect(apiClient.get).toHaveBeenCalledWith("/invoices/i1");
    expect(apiClient.patch).toHaveBeenCalledWith("/invoices/i1", input);
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/i1/duplicate");
    expect(apiClient.delete).toHaveBeenCalledWith("/invoices/i1");
  });
});
