import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { getInformationBanner } from "@/api/informationBanner";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("public information banner API", () => {
  it("reads the banner with GET", async () => {
    const banner = { login: { message: "Hi", icon: "info", color: "blue" }, site_wide: null };
    fetchMock.mockResolvedValue(new Response(JSON.stringify(banner), { status: 200 }));

    const result = await getInformationBanner();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/information-banner");
    expect(init.method).toBe("GET");
    expect(result).toEqual(banner);
  });

  it("fails with an ApiError and tries nothing else when the server errors", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 500 }));

    await expect(getInformationBanner()).rejects.toBeInstanceOf(ApiError);
    // No session refresh, no second request: the sign-in page must not react to this.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
