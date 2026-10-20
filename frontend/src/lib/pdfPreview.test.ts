import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  OBJECT_URL_LIFETIME_MS,
  openPdfPreview,
  previewErrorMessage,
  type PreviewTab,
  type PreviewTarget,
} from "@/lib/pdfPreview";

function fakeTarget(options: { firstTab?: boolean; secondTab?: boolean } = {}) {
  const events: string[] = [];
  const tab: PreviewTab = {
    navigate: (url) => events.push(`navigate ${url}`),
    close: () => events.push("close"),
  };
  const later: (() => void)[] = [];
  let opened = 0;
  const target: PreviewTarget = {
    open: (url) => {
      opened += 1;
      events.push(`open ${url}`);
      const allowed = opened === 1 ? (options.firstTab ?? true) : (options.secondTab ?? true);
      return allowed ? tab : null;
    },
    createObjectUrl: () => {
      events.push("create url");
      return "blob:pdf";
    },
    revokeObjectUrl: (url) => events.push(`revoke ${url}`),
    later: (callback, ms) => {
      events.push(`later ${ms}`);
      later.push(callback);
    },
  };
  return { target, events, later };
}

describe("openPdfPreview", () => {
  it("opens the tab before the PDF exists, then points it at the PDF", async () => {
    const { target, events } = fakeTarget();
    const makePdf = vi.fn(async () => {
      events.push("made");
      return new Blob(["%PDF"]);
    });
    await expect(openPdfPreview(makePdf, target)).resolves.toBe("opened");
    expect(events.slice(0, 2)).toEqual(["open about:blank", "made"]);
    expect(events).toContain("navigate blob:pdf");
  });

  it("releases the object URL after a while", async () => {
    const { target, events, later } = fakeTarget();
    await openPdfPreview(async () => new Blob(["x"]), target);
    expect(events).toContain(`later ${OBJECT_URL_LIFETIME_MS}`);
    later[0]();
    expect(events).toContain("revoke blob:pdf");
  });

  it("closes the tab and passes the error on when the PDF cannot be made", async () => {
    const { target, events } = fakeTarget();
    const failure = new ApiError(503, "The PDF engine is not available");
    await expect(
      openPdfPreview(async () => {
        throw failure;
      }, target),
    ).rejects.toBe(failure);
    expect(events).toContain("close");
    expect(events.some((e) => e.startsWith("navigate"))).toBe(false);
  });

  it("tries again with the PDF when the first tab was blocked", async () => {
    const { target, events } = fakeTarget({ firstTab: false });
    await expect(openPdfPreview(async () => new Blob(["x"]), target)).resolves.toBe("opened");
    expect(events).toContain("open blob:pdf");
  });

  it("says so when no tab can be opened", async () => {
    const { target } = fakeTarget({ firstTab: false, secondTab: false });
    await expect(openPdfPreview(async () => new Blob(["x"]), target)).resolves.toBe("blocked");
  });
});

describe("previewErrorMessage", () => {
  const t = (key: string) => key;

  it("names the engine when the server says it is unavailable", () => {
    expect(previewErrorMessage(new ApiError(503, "anything"), t)).toBe(
      "The PDF engine is not available",
    );
  });

  it("shows the server's reason for other rejections", () => {
    expect(previewErrorMessage(new ApiError(422, "The payee currency is not valid"), t)).toBe(
      "The payee currency is not valid",
    );
  });

  it("falls back to a generic message", () => {
    expect(previewErrorMessage(new TypeError("boom"), t)).toBe(
      "Failed to prepare the preview.",
    );
  });
});
