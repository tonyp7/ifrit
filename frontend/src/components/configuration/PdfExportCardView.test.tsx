import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../../public/locales/en/common.json";
import configuration from "../../../public/locales/en/configuration.json";
import {
  PdfExportCardView,
  type PdfExportCardViewProps,
} from "@/components/configuration/PdfExportCardView";

const baseProps: PdfExportCardViewProps = {
  loading: false,
  loadFailed: false,
  exportLogo: true,
  heightMm: 20,
  saving: false,
  onExportLogoChange: vi.fn(),
  onHeightChange: vi.fn(),
  onHeightCommit: vi.fn(),
  onRetry: vi.fn(),
};

// Real translations, and any key the card uses that is missing from the locale files
// is recorded so the test fails on it.
function render(overrides: Partial<PdfExportCardViewProps> = {}) {
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
      <PdfExportCardView {...baseProps} {...overrides} />
    </I18nextProvider>,
  );
  expect(missing).toEqual([]);
  return html;
}

// The `disabled` attribute of the element carrying the given role.
function isDisabled(html: string, role: "switch" | "slider") {
  const tag = new RegExp(`<[^>]*role="${role}"[^>]*>`).exec(html)?.[0] ?? "";
  return /\sdisabled(=|\s|>)/.test(tag) || /data-disabled/.test(tag);
}

describe("PdfExportCardView", () => {
  it("is titled PDF Report Export with the switch above the slider", () => {
    const html = render();

    expect(html).toContain("PDF Report Export");
    const switchAt = html.indexOf("Insert organization logo in exported PDF");
    const sliderAt = html.indexOf("Logo height, in mm");
    expect(switchAt).toBeGreaterThan(-1);
    expect(sliderAt).toBeGreaterThan(switchAt);
  });

  it("shows the height on the right of the label, in the same row", () => {
    const html = render({ heightMm: 20 });

    // Label then value, with nothing between them but the row's own closing/opening tags.
    expect(html).toMatch(/Logo height, in mm<\/label>\s*<span[^>]*>20<\/span>/);
    expect(html).toContain("justify-between");
  });

  it("offers 1 to 60 mm", () => {
    const html = render({ heightMm: 20 });

    // The thumb's current value is only drawn on the client (checked live); the range is
    // already in the server-rendered markup.
    expect(html).toContain('aria-valuemin="1"');
    expect(html).toContain('aria-valuemax="60"');
  });

  it("names the slider's thumb after its label", () => {
    const html = render();

    const label = /<label[^>]*id="([^"]+)"[^>]*>Logo height, in mm<\/label>/.exec(html);
    const thumb = /<[^>]*role="slider"[^>]*>/.exec(html)?.[0] ?? "";
    expect(label).not.toBeNull();
    expect(thumb).toContain(`aria-labelledby="${label?.[1]}"`);
  });

  it("reflects the switch state", () => {
    expect(render({ exportLogo: true })).toContain('aria-checked="true"');
    expect(render({ exportLogo: false })).toContain('aria-checked="false"');
  });

  it("disables both controls and shows no value while loading", () => {
    const html = render({ loading: true, exportLogo: null, heightMm: null });

    expect(isDisabled(html, "switch")).toBe(true);
    expect(isDisabled(html, "slider")).toBe(true);
    expect(html).toMatch(/data-testid="logo-height-value"[^>]*><\/span>/);
  });

  it("keeps the slider visible with its value, but disabled, while the logo is off", () => {
    const html = render({ exportLogo: false, heightMm: 35 });

    expect(isDisabled(html, "slider")).toBe(true);
    expect(isDisabled(html, "switch")).toBe(false);
    expect(html).toMatch(/data-testid="logo-height-value"[^>]*>35</);
  });

  it("enables both controls once loaded with the logo on", () => {
    const html = render();

    expect(isDisabled(html, "switch")).toBe(false);
    expect(isDisabled(html, "slider")).toBe(false);
  });

  it("locks both controls while a save is in flight", () => {
    const html = render({ saving: true });

    expect(isDisabled(html, "switch")).toBe(true);
    expect(isDisabled(html, "slider")).toBe(true);
  });

  it("shows a message and a retry when the settings cannot be loaded, and no value", () => {
    const html = render({ loadFailed: true, exportLogo: null, heightMm: null });

    expect(html).toContain("Couldn&#x27;t load the PDF export settings.");
    expect(html).toContain("Try again");
    expect(isDisabled(html, "switch")).toBe(true);
    expect(isDisabled(html, "slider")).toBe(true);
  });

  it("shows no error and no retry when loading went well", () => {
    const html = render();

    expect(html).not.toContain("Try again");
  });

  it("does not claim that exported PDFs already follow these settings", () => {
    const html = render();

    expect(html).not.toMatch(/applied|takes effect|will be used/i);
  });
});
