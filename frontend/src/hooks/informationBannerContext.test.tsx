import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { SiteWideBanner } from "@/components/InformationBannerProvider";
import {
  createBannerLoader,
  InformationBannerContext,
  refreshAfterSave,
  useInformationBannerContext,
} from "@/hooks/informationBannerContext";
import type { PublicBanner } from "@/types/settings";

function banner(message: string): PublicBanner {
  return { login: null, site_wide: { message, icon: "info", color: "blue" } };
}

// A promise that is settled by hand, to decide which of two reads finishes first.
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe("createBannerLoader", () => {
  it("returns what the server answered", async () => {
    const load = createBannerLoader(() => Promise.resolve(banner("Hello")));
    expect(await load()).toEqual(banner("Hello"));
  });

  it("returns null when a read fails, so the caller keeps what it shows", async () => {
    const load = createBannerLoader(() => Promise.reject(new ApiError(500, "Server error")));
    expect(await load()).toBeNull();
  });

  it("hands back only the newest answer, whichever read finishes first", async () => {
    const first = deferred<PublicBanner>();
    const second = deferred<PublicBanner>();
    const reads = [first.promise, second.promise];
    const load = createBannerLoader(() => reads.shift()!);

    const older = load();
    const newer = load();
    second.resolve(banner("Newer"));
    first.resolve(banner("Older"));

    expect(await newer).toEqual(banner("Newer"));
    expect(await older).toBeNull();
  });

  it("hands back the newest answer when the older read finishes first too", async () => {
    const first = deferred<PublicBanner>();
    const second = deferred<PublicBanner>();
    const reads = [first.promise, second.promise];
    const load = createBannerLoader(() => reads.shift()!);

    const older = load();
    const newer = load();
    first.resolve(banner("Older"));
    second.resolve(banner("Newer"));

    expect(await older).toBeNull();
    expect(await newer).toEqual(banner("Newer"));
  });
});

describe("refreshAfterSave", () => {
  it("refreshes after a save the server accepted", () => {
    const refresh = vi.fn();
    refreshAfterSave({ ok: true }, refresh);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("does not refresh after a rejected save", () => {
    const refresh = vi.fn();
    refreshAfterSave({ ok: false, rejected: true, message: "Too long" }, refresh);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("does not refresh after a failure to reach the server", () => {
    const refresh = vi.fn();
    refreshAfterSave({ ok: false, rejected: false }, refresh);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("does not refresh when nothing was sent", () => {
    const refresh = vi.fn();
    refreshAfterSave(null, refresh);
    expect(refresh).not.toHaveBeenCalled();
  });
});

describe("InformationBannerContext", () => {
  it("is a harmless no-op outside a provider", () => {
    function Probe() {
      const { banner: current, refresh } = useInformationBannerContext();
      refresh();
      return <span>{String(current)}</span>;
    }
    expect(renderToStaticMarkup(<Probe />)).toContain("null");
  });
});

describe("SiteWideBanner", () => {
  function render(value: PublicBanner | null) {
    return renderToStaticMarkup(
      <InformationBannerContext value={{ banner: value, refresh: vi.fn() }}>
        <SiteWideBanner />
      </InformationBannerContext>,
    );
  }

  it("shows the site-wide member as a strip", () => {
    const html = render(banner("Maintenance"));

    expect(html).toContain("Maintenance");
    expect(html).toContain('role="status"');
    expect(html).not.toContain("<button");
  });

  it("shows nothing without a banner or when the site-wide member is null", () => {
    expect(render(null)).toBe("");
    expect(render({ login: null, site_wide: null })).toBe("");
  });

  it("ignores the login member", () => {
    const html = render({
      login: { message: "Only on sign-in", icon: "info", color: "neutral" },
      site_wide: null,
    });

    expect(html).toBe("");
  });
});
