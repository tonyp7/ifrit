import { apiClient } from "@/api/client";
import type {
  BillingContext,
  GenerateInput,
  GenerateResult,
  InvoiceableProject,
  InvoiceDetail,
  InvoiceInput,
  InvoiceListResponse,
  InvoiceStatus,
  IssuePreview,
} from "@/types/invoice";

export function listInvoices(params: {
  page?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  projectId?: string;
  statuses?: InvoiceStatus[];
  search?: string;
}) {
  const query = new URLSearchParams();
  query.set("page", String(params.page ?? 1));
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
  if (params.projectId) query.set("project_id", params.projectId);
  for (const status of params.statuses ?? []) query.append("status", status);
  if (params.search) query.set("search", params.search);
  return apiClient.get<InvoiceListResponse>(`/invoices?${query.toString()}`);
}

/** Without `invoiced`, the projects a new invoice can be started for; with it, every
 * project that has invoices (the list's filter). */
export function listInvoiceProjects(params: { search?: string; invoiced?: boolean } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.invoiced) query.set("invoiced", "true");
  const suffix = query.size ? `?${query.toString()}` : "";
  return apiClient.get<InvoiceableProject[]>(`/invoices/projects${suffix}`);
}

export function getBillingContext(projectId: string) {
  return apiClient.get<BillingContext>(`/invoices/projects/${projectId}`);
}

export function generateLines(payload: GenerateInput) {
  return apiClient.post<GenerateResult>("/invoices/generate", payload);
}

export function getInvoice(invoiceId: string) {
  return apiClient.get<InvoiceDetail>(`/invoices/${invoiceId}`);
}

export function createInvoice(payload: InvoiceInput) {
  return apiClient.post<InvoiceDetail>("/invoices", payload);
}

export function updateInvoice(invoiceId: string, payload: InvoiceInput) {
  return apiClient.patch<InvoiceDetail>(`/invoices/${invoiceId}`, payload);
}

export function deleteInvoice(invoiceId: string) {
  return apiClient.delete<void>(`/invoices/${invoiceId}`);
}

export function duplicateInvoice(invoiceId: string) {
  return apiClient.post<InvoiceDetail>(`/invoices/${invoiceId}/duplicate`);
}

export function getIssuePreview(invoiceId: string) {
  return apiClient.get<IssuePreview>(`/invoices/${invoiceId}/issue-preview`);
}

export function issueInvoice(invoiceId: string) {
  return apiClient.post<InvoiceDetail>(`/invoices/${invoiceId}/issue`);
}

/** An empty reason is sent as none. */
export function voidInvoice(invoiceId: string, reason: string) {
  return apiClient.post<InvoiceDetail>(`/invoices/${invoiceId}/void`, {
    reason: reason.trim() || null,
  });
}
