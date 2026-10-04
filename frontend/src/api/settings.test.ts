import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPdfExportSettings, patchPdfExportSettings } from "@/api/settings";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ export_logo: true, logo_height_mm: 25 }), {
      status: 200,
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PDF export settings API", () => {
  it("reads the group with GET", async () => {
    const result = await getPdfExportSettings();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/settings/pdf-export");
    expect(init.method).toBe("GET");
    expect(result).toEqual({ export_logo: true, logo_height_mm: 25 });
  });

  it("sends only the changed setting with PATCH and returns the whole group", async () => {
    const result = await patchPdfExportSettings({ logo_height_mm: 25 });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/settings/pdf-export");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ logo_height_mm: 25 });
    expect(result).toEqual({ export_logo: true, logo_height_mm: 25 });
  });

  it("surfaces the server's reason for a rejected value", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [{ loc: ["logo_height_mm"], msg: "Input should be at most 60", type: "x" }],
        }),
        { status: 422 },
      ),
    );

    await expect(patchPdfExportSettings({ logo_height_mm: 61 })).rejects.toMatchObject({
      status: 422,
      message: "Input should be at most 60",
    });
  });
});
