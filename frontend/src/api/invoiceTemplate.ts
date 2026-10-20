import { ApiError, apiClient } from "@/api/client";
import type {
  InvoiceTemplateInfo,
  InvoiceTemplateSaved,
  TemplateFinding,
  TemplateRejection,
  TemplateToken,
} from "@/types/invoiceTemplate";

const PATH = "/invoice-template";

export function getInvoiceTemplate() {
  return apiClient.get<InvoiceTemplateInfo>(PATH);
}

export function getTemplateTokens() {
  return apiClient.get<TemplateToken[]>(`${PATH}/tokens`);
}

/** The template in use as an .odt, with the file name the server gives it. */
export function downloadTemplate() {
  return apiClient.getBlob(`${PATH}/file`);
}

function body(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

/** The sample invoice made with `file`, and the warnings about it. Nothing is stored. */
export async function previewTemplate(
  file: File,
): Promise<{ blob: Blob; warnings: TemplateFinding[] }> {
  const { blob, headers } = await apiClient.postBlob(`${PATH}/preview`, body(file));
  return { blob, warnings: parseWarnings(headers.get("X-Template-Warnings")) };
}

export function uploadTemplate(file: File) {
  return apiClient.upload<InvoiceTemplateSaved>(PATH, body(file), { method: "PUT" });
}

/** Reset to default: discards an uploaded template. */
export function resetTemplate() {
  return apiClient.delete<void>(PATH);
}

function parseWarnings(header: string | null): TemplateFinding[] {
  if (!header) return [];
  try {
    const parsed: unknown = JSON.parse(header);
    return Array.isArray(parsed) ? (parsed as TemplateFinding[]) : [];
  } catch {
    return [];
  }
}

/** The problems and warnings of a rejected template, or null for any other failure. */
export function templateRejection(err: unknown): TemplateRejection | null {
  if (!(err instanceof ApiError) || err.status !== 422) return null;
  const detail = err.detail as Partial<TemplateRejection> | null;
  if (!detail || !Array.isArray(detail.problems)) return null;
  return { problems: detail.problems, warnings: detail.warnings ?? [] };
}
