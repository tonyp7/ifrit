import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { loadBanner } from "@/hooks/useInformationBanner";
import type { PublicBanner } from "@/types/settings";

const banner: PublicBanner = {
  login: { message: "Hello", icon: "info", color: "blue" },
  site_wide: null,
};

describe("loadBanner", () => {
  it("returns what the server answered", async () => {
    expect(await loadBanner(() => Promise.resolve(banner))).toEqual(banner);
  });

  it("returns null, without throwing, when the request fails", async () => {
    const read = vi.fn().mockRejectedValue(new ApiError(500, "Server error"));
    expect(await loadBanner(read)).toBeNull();
  });

  it("returns null when the network is down", async () => {
    expect(
      await loadBanner(() => Promise.reject(new TypeError("Failed to fetch"))),
    ).toBeNull();
  });

  it("makes exactly one request", async () => {
    const read = vi.fn().mockResolvedValue(banner);
    await loadBanner(read);
    expect(read).toHaveBeenCalledTimes(1);
  });
});
