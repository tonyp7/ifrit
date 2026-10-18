import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import {
  createInvoice,
  deleteInvoice,
  duplicateInvoice,
  generateLines,
  getBillingContext,
  getInvoice,
  getIssuePreview,
  issueInvoice,
  listInvoiceProjects,
  listInvoices,
  updateInvoice,
  voidInvoice,
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
  taxes: [
    {
      label: "VAT",
      base_mode: "subtotal",
      rate: "21",
      amount: null,
      amount_set_by_hand: false,
    },
  ],
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
      kind: "time" as const,
      project_id: "p1",
      service_line_ids: ["s1"],
      period_start: "2026-09-01",
      period_end: "2026-09-30",
    };
    void generateLines(generate);
    expect(apiClient.get).toHaveBeenCalledWith("/invoices/projects/p1");
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/generate", generate);
    const milestone = {
      kind: "milestone" as const,
      project_id: "p1",
      milestone_ids: ["m1", "m2"],
    };
    void generateLines(milestone);
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/generate", milestone);
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

  it("filters the list by status, one parameter per status", () => {
    void listInvoices({ statuses: ["draft", "void"] });
    expect(apiClient.get).toHaveBeenCalledWith("/invoices?page=1&status=draft&status=void");
  });

  it("sends the search text encoded, and leaves it out when empty", () => {
    void listInvoices({ search: "50% & co", statuses: ["draft"] });
    void listInvoices({ search: "" });
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      "/invoices?page=1&status=draft&search=50%25+%26+co",
    );
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/invoices?page=1");
  });

  it("previews, issues and voids", () => {
    void getIssuePreview("i1");
    void issueInvoice("i1");
    void voidInvoice("i1", "  Wrong period ");
    void voidInvoice("i2", "   ");
    expect(apiClient.get).toHaveBeenCalledWith("/invoices/i1/issue-preview");
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/i1/issue");
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/i1/void", {
      reason: "Wrong period",
    });
    expect(apiClient.post).toHaveBeenCalledWith("/invoices/i2/void", { reason: null });
  });
});
