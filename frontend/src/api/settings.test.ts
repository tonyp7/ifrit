import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getGeneralSettings,
  getInformationBannerSettings,
  getInvoicingSettings,
  getPdfExportSettings,
  patchGeneralSettings,
  patchInformationBannerSettings,
  patchInvoicingSettings,
  patchPdfExportSettings,
} from "@/api/settings";

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

describe("general and invoicing settings API", () => {
  // Two requests per test, and a Response body can only be read once.
  beforeEach(() => {
    fetchMock.mockImplementation(() => Promise.resolve(new Response("{}", { status: 200 })));
  });

  it("reads and patches the general group", async () => {
    await getGeneralSettings();
    await patchGeneralSettings({ standard_workday_seconds: 25200 });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/settings/general");
    expect(fetchMock.mock.calls[0][1].method).toBe("GET");
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/settings/general");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ standard_workday_seconds: 25200 });
  });

  it("reads and patches the invoicing group", async () => {
    await getInvoicingSettings();
    await patchInvoicingSettings({ document_name: "Tax Invoice" });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/settings/invoicing");
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/settings/invoicing");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ document_name: "Tax Invoice" });
  });
});

describe("information banner settings API", () => {
  it("reads the group with GET", async () => {
    await getInformationBannerSettings();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/settings/information-banner");
    expect(init.method).toBe("GET");
  });

  it("sends only the keys given with PATCH", async () => {
    await patchInformationBannerSettings({ message: "Hello", color: "blue" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/settings/information-banner");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ message: "Hello", color: "blue" });
  });
});
