import { ApiError } from "@/api/client";

/** What the browser offers for showing a file in another tab. Injected so the order of
 * events can be tested without a browser. */
export interface PreviewTarget {
  open: (url: string) => PreviewTab | null;
  createObjectUrl: (blob: Blob) => string;
  revokeObjectUrl: (url: string) => void;
  /** Runs `callback` after `ms`; the object URL is released then. */
  later: (callback: () => void, ms: number) => void;
}

export interface PreviewTab {
  navigate: (url: string) => void;
  close: () => void;
}

/** How long the object URL stays valid: long enough for the tab to load the file. */
export const OBJECT_URL_LIFETIME_MS = 60_000;

export const browserTarget: PreviewTarget = {
  open(url) {
    const tab = window.open(url, "_blank");
    if (!tab) return null;
    // The tab starts on the app's own origin, so it must not be able to reach back.
    tab.opener = null;
    return { navigate: (next) => (tab.location.href = next), close: () => tab.close() };
  },
  createObjectUrl: (blob) => URL.createObjectURL(blob),
  revokeObjectUrl: (url) => URL.revokeObjectURL(url),
  later: (callback, ms) => void window.setTimeout(callback, ms),
};

/**
 * Opens a PDF in a new tab. The tab is opened first, in the click's own turn, because a
 * browser blocks a tab opened after an `await`; it is pointed at the PDF once that arrives
 * and closed again when making the PDF failed.
 */
export async function openPdfPreview(
  makePdf: () => Promise<Blob>,
  target: PreviewTarget = browserTarget,
): Promise<"opened" | "blocked"> {
  const tab = target.open("about:blank");
  let url: string;
  try {
    url = target.createObjectUrl(await makePdf());
  } catch (err) {
    tab?.close();
    throw err;
  }
  target.later(() => target.revokeObjectUrl(url), OBJECT_URL_LIFETIME_MS);
  if (tab) {
    tab.navigate(url);
    return "opened";
  }
  // The first tab was blocked; the user's click may still allow this one.
  return target.open(url) ? "opened" : "blocked";
}

/** The sentence the form shows when a preview could not be made. */
export function previewErrorMessage(err: unknown, t: (key: string) => string): string {
  if (err instanceof ApiError) {
    return err.status === 503 ? t("The PDF engine is not available") : err.message;
  }
  return t("Failed to prepare the preview.");
}
