import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import { canDownloadPdf, isPdfUnavailable } from "@/lib/invoicePdf";

describe("canDownloadPdf", () => {
  it("is true for an issued or void invoice that has a PDF", () => {
    expect(canDownloadPdf({ status: "issued", has_pdf: true })).toBe(true);
    expect(canDownloadPdf({ status: "void", has_pdf: true })).toBe(true);
  });

  it("is false for a draft, which is previewed instead", () => {
    expect(canDownloadPdf({ status: "draft", has_pdf: false })).toBe(false);
  });

  it("is false for an invoice issued before PDFs were kept", () => {
    expect(canDownloadPdf({ status: "issued", has_pdf: false })).toBe(false);
    expect(canDownloadPdf({ status: "void", has_pdf: false })).toBe(false);
  });
});

describe("isPdfUnavailable", () => {
  it("recognises the 503 an issue answers when the PDF could not be made", () => {
    expect(isPdfUnavailable(new ApiError(503, "x"))).toBe(true);
  });

  it("is false for any other failure", () => {
    expect(isPdfUnavailable(new ApiError(409, "x"))).toBe(false);
    expect(isPdfUnavailable(new Error("x"))).toBe(false);
  });
});
