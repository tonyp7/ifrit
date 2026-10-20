import { ApiError } from "@/api/client";
import type { InvoiceStatus } from "@/types/invoice";

/** A PDF can be downloaded once an invoice is issued (or void) and has one: a draft is
 * previewed instead, and an invoice issued before PDFs were kept has nothing to download. */
export function canDownloadPdf(invoice: { status: InvoiceStatus; has_pdf: boolean }): boolean {
  return invoice.status !== "draft" && invoice.has_pdf;
}

/** Issuing answers 503 when the PDF could not be made, and then nothing was issued: the
 * confirmation stays open so the user can try again. */
export function isPdfUnavailable(err: unknown): boolean {
  return err instanceof ApiError && err.status === 503;
}
