import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../../public/locales/en/common.json";
import configuration from "../../../public/locales/en/configuration.json";
import {
  OrganizationLogoCardView,
  type OrganizationLogoCardViewProps,
} from "@/components/configuration/OrganizationLogoCardView";

const logo = {
  file_id: "11111111-2222-3333-4444-555555555555",
  original_filename: "logo.png",
  content_type: "image/png",
  size_bytes: 1234,
  uploaded_at: "2026-10-01T00:00:00Z",
};

const idle = { status: "idle", progress: 0, error: null } as const;

const baseProps: OrganizationLogoCardViewProps = {
  logo: null,
  loading: false,
  loadFailed: false,
  upload: idle,
  removing: false,
  onBrowse: vi.fn(),
  onRetry: vi.fn(),
  onRemove: vi.fn(),
};

// Real translations, and any key the card uses that is missing from the locale files
// is recorded so the test fails on it.
function render(overrides: Partial<OrganizationLogoCardViewProps> = {}) {
  const missing: string[] = [];
  const i18n = createInstance();
  void i18n.use(initReactI18next).init({
    lng: "en",
    resources: { en: { common, configuration } },
    defaultNS: "common",
    initAsync: false,
    saveMissing: true,
    missingKeyHandler: (_lngs, ns, key) => missing.push(`${ns}:${key}`),
    interpolation: { escapeValue: false },
  });
  const html = renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>
      <OrganizationLogoCardView {...baseProps} {...overrides} />
    </I18nextProvider>,
  );
  expect(missing).toEqual([]);
  return html;
}

describe("OrganizationLogoCardView", () => {
  it("is titled Organization Logo and names the accepted formats", () => {
    const html = render();

    expect(html).toContain("Organization Logo");
    expect(html).toContain("JPEG, PNG or WebP.");
  });

  it("shows the empty state, Browse and no Remove when there is no logo", () => {
    const html = render();

    expect(html).toContain("No logo uploaded");
    expect(html).toContain("Browse…");
    expect(html).not.toContain("<img");
    expect(html).not.toContain(">Remove<");
  });

  it("shows the stored logo contained in a 3:2 box, and Remove", () => {
    const html = render({ logo });

    expect(html).toContain(`src="/api/files/${logo.file_id}/content"`);
    expect(html).toContain("object-contain");
    expect(html).not.toContain("object-cover");
    // Radix AspectRatio renders its ratio as padding-bottom: 100 / 1.5 = 66.67%.
    expect(html).toContain("padding-bottom:66.6666");
    expect(html).toContain(">Remove<");
    expect(html).not.toContain("No logo uploaded");
  });

  it("takes the content area's width: no margin or width cap of its own", () => {
    const html = render({ logo });

    // The card's root carries no classes beyond the shadcn defaults; the page supplies
    // padding and spacing.
    expect(html).toContain(
      '<div class="rounded-lg border bg-card text-card-foreground shadow-sm">',
    );
    expect(html).not.toContain("max-w-2xl");
    expect(html).not.toContain("m-4");
  });

  it("uses the Projects heading style for its title", () => {
    const html = render();

    expect(html).toMatch(
      /class="[^"]*\btext-lg\b[^"]*\bfont-medium\b[^"]*">Organization Logo</,
    );
    expect(html).not.toMatch(/class="[^"]*\btext-2xl\b[^"]*">Organization Logo</);
    expect(html).not.toMatch(/class="[^"]*\bfont-semibold\b[^"]*">Organization Logo</);
  });

  it("caps the picture's width at 176px on mobile and 240px beyond, with Browse below on mobile and beside it on wider screens", () => {
    const html = render({ logo });

    expect(html).toContain("w-44");
    expect(html).toContain("sm:w-60");
    expect(html).not.toContain("w-28");
    expect(html).not.toContain("sm:w-40");
    expect(html).toContain("flex-col");
    expect(html).toContain("sm:flex-row");
  });

  it("keeps Browse and Remove beside the picture, not pushed to the card's edge", () => {
    const html = render({ logo });

    expect(html).not.toContain("justify-between");
    expect(html).not.toContain("ml-auto");
  });

  it("shows a blank box, with Browse disabled and no Remove, while the logo is being looked up", () => {
    const html = render({ loading: true });

    expect(html).not.toContain("No logo uploaded");
    expect(html).not.toContain("<img");
    expect(html).not.toContain(">Remove<");
    expect(html).toMatch(/<button[^>]*\sdisabled=""[^>]*>(?:(?!<\/button>).)*Browse…/s);
    // The box keeps its size so nothing shifts when the result arrives.
    expect(html).toContain("padding-bottom:66.6666");
  });

  it("shows the empty state, an enabled Browse and the load alert after a failed lookup", () => {
    const html = render({ loading: false, loadFailed: true });

    expect(html).toContain("No logo uploaded");
    expect(html).not.toMatch(/<button[^>]*\sdisabled=""[^>]*>(?:(?!<\/button>).)*Browse…/s);
  });

  it("restricts the file chooser to JPEG, PNG and WebP", () => {
    const html = render();

    expect(html).toContain('accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"');
  });

  it("shows a progress bar and disables Browse while uploading", () => {
    const html = render({ logo, upload: { status: "uploading", progress: 42, error: null } });

    expect(html).toContain('role="progressbar"');
    expect(html).toContain('aria-label="Uploading logo"');
    expect(html).not.toContain('aria-label="Browse…"');
    expect(html).toContain("Uploading… 42%");
    expect(html).toMatch(/<button[^>]*\sdisabled=""[^>]*>(?:(?!<\/button>).)*Browse…/s);
  });

  it("shows the server's reason for a rejected file, without a retry", () => {
    const html = render({
      upload: { status: "rejected", progress: 0, error: "This file type is not allowed" },
    });

    expect(html).toContain("Upload rejected");
    expect(html).toContain("This file type is not allowed");
    expect(html).not.toContain("Try again");
  });

  it("shows a distinct message with a retry for a network failure", () => {
    const html = render({ upload: { status: "error", progress: 0, error: "Network error" } });

    expect(html).toContain("Upload failed");
    expect(html).toContain("Check your connection and try again.");
    expect(html).toContain("Try again");
    expect(html).not.toContain("Upload rejected");
  });

  it("shows a spinner and disables the actions while removing", () => {
    const html = render({ logo, removing: true });

    expect(html).toContain("Removing…");
    expect(html).toContain('role="status"');
  });

  it("says so when the current logo could not be loaded", () => {
    expect(render({ loadFailed: true })).toContain("load the logo.");
  });
});
