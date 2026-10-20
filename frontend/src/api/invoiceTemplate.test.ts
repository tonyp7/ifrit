import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiClient } from "@/api/client";
import {
  downloadTemplate,
  getInvoiceTemplate,
  getTemplateTokens,
  previewTemplate,
  resetTemplate,
  templateRejection,
  uploadTemplate,
} from "@/api/invoiceTemplate";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    apiClient: {
      get: vi.fn(),
      getBlob: vi.fn(),
      postBlob: vi.fn(),
      upload: vi.fn(),
      delete: vi.fn(),
    },
  };
});

beforeEach(() => vi.clearAllMocks());

const file = new File(["odt"], "acme.odt");

describe("invoice template API", () => {
  it("reads the template in use and the placeholder catalogue", () => {
    void getInvoiceTemplate();
    void getTemplateTokens();
    expect(apiClient.get).toHaveBeenNthCalledWith(1, "/invoice-template");
    expect(apiClient.get).toHaveBeenNthCalledWith(2, "/invoice-template/tokens");
  });

  it("downloads the template in use", () => {
    void downloadTemplate();
    expect(apiClient.getBlob).toHaveBeenCalledWith("/invoice-template/file");
  });

  it("previews by posting the file as multipart and reads the warnings header", async () => {
    const blob = new Blob(["%PDF"]);
    const warnings = [{ part: "template", message: "No mark", snippet: null }];
    vi.mocked(apiClient.postBlob).mockResolvedValue({
      blob,
      filename: null,
      headers: new Headers({ "X-Template-Warnings": JSON.stringify(warnings) }),
    });

    const result = await previewTemplate(file);

    const [path, form] = vi.mocked(apiClient.postBlob).mock.calls[0];
    expect(path).toBe("/invoice-template/preview");
    expect((form as FormData).get("file")).toBe(file);
    expect(result).toEqual({ blob, warnings });
  });

  it("treats a missing or damaged warnings header as no warnings", async () => {
    const blob = new Blob(["%PDF"]);
    for (const value of [null, "not json", '{"a":1}']) {
      const headers = new Headers();
      if (value) headers.set("X-Template-Warnings", value);
      vi.mocked(apiClient.postBlob).mockResolvedValue({ blob, filename: null, headers });
      expect((await previewTemplate(file)).warnings).toEqual([]);
    }
  });

  it("uploads with PUT and resets with DELETE", () => {
    void uploadTemplate(file);
    void resetTemplate();
    const [path, form, options] = vi.mocked(apiClient.upload).mock.calls[0];
    expect(path).toBe("/invoice-template");
    expect((form as FormData).get("file")).toBe(file);
    expect(options).toEqual({ method: "PUT" });
    expect(apiClient.delete).toHaveBeenCalledWith("/invoice-template");
  });
});

describe("templateRejection", () => {
  it("reads the problems and warnings of a 422", () => {
    const problems = [
      { part: "content.xml", message: "Unknown placeholder", snippet: "{{x}}" },
    ];
    const err = new ApiError(422, "The template cannot be used", {
      message: "The template cannot be used",
      problems,
      warnings: [],
    });
    expect(templateRejection(err)).toEqual({ problems, warnings: [] });
  });

  it("is null for any other failure", () => {
    expect(templateRejection(new ApiError(503, "The PDF engine is not available"))).toBeNull();
    expect(
      templateRejection(new ApiError(422, "plain sentence", "plain sentence")),
    ).toBeNull();
    expect(templateRejection(new Error("x"))).toBeNull();
  });
});
