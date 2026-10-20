import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiError } from "@/api/client";

vi.mock("@/api/sessionEvents", () => ({ notifySessionExpired: vi.fn() }));

afterEach(() => vi.unstubAllGlobals());

function stubFetch(...responses: Response[]) {
  const fetchMock = vi.fn();
  for (const response of responses) fetchMock.mockResolvedValueOnce(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("apiClient.postBlob", () => {
  it("posts the body as JSON and returns the file and its name", async () => {
    const fetchMock = stubFetch(
      new Response("%PDF-1.7", {
        headers: { "Content-Disposition": 'inline; filename="draft-1.pdf"' },
      }),
    );
    const result = await apiClient.postBlob("/invoices/preview-pdf", { a: 1 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/invoices/preview-pdf");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(await result.blob.text()).toBe("%PDF-1.7");
    expect(result.filename).toBe("draft-1.pdf");
  });

  it("turns an error response into an ApiError with the server's message", async () => {
    stubFetch(
      new Response(JSON.stringify({ detail: "The PDF engine is not available" }), {
        status: 503,
      }),
    );
    await expect(apiClient.postBlob("/invoices/preview-pdf", {})).rejects.toMatchObject({
      status: 503,
      message: "The PDF engine is not available",
    });
  });

  it("is an ApiError instance", async () => {
    stubFetch(new Response("{}", { status: 422 }));
    await expect(apiClient.postBlob("/x", {})).rejects.toBeInstanceOf(ApiError);
  });
});
