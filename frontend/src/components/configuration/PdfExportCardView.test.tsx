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

  // Opening tag of the element holding the control or label at `at`: the row it sits in.
  function rowTagAt(html: string, at: number) {
    const start = html.lastIndexOf("<div", at);
    return html.slice(start, html.indexOf(">", start) + 1);
  }

  it("puts the switch first on its row with its label directly after it", () => {
    const html = render();

    const switchAt = html.indexOf('role="switch"');
    const labelAt = html.indexOf("Insert organization logo in exported PDF");
    expect(switchAt).toBeGreaterThan(-1);
    expect(labelAt).toBeGreaterThan(switchAt);

    // The label belongs to the switch, and only the switch's own markup lies between them.
    const switchId = /role="switch"[^>]*\sid="([^"]+)"|\sid="([^"]+)"[^>]*role="switch"/.exec(
      html,
    );
    const id = switchId?.[1] ?? switchId?.[2];
    expect(html).toContain(`for="${id}"`);
    const between = html.slice(switchAt, html.lastIndexOf("<label", labelAt));
    expect(between).not.toContain("<label");
    expect(between.match(/<div/g)).toBeNull();
  });

  it("does not spread the switch and its label to the two ends of the row", () => {
    const html = render();

    expect(rowTagAt(html, html.indexOf('role="switch"'))).not.toContain("justify-between");
    // The slider's row keeps its label on the left and the value on the right.
    expect(rowTagAt(html, html.indexOf("Logo height, in mm"))).toContain("justify-between");
  });

  it("lets the label dim with the switch", () => {
    const html = render();

    // The label dims through `peer-disabled`, which only applies to a label that follows
    // the disabled switch (a `peer`) in the markup, so both halves are checked.
    const switchTag = /<[^>]*role="switch"[^>]*>/.exec(html)?.[0] ?? "";
    const labelTag =
      /<label[^>]*>(?=Insert organization logo in exported PDF)/.exec(html)?.[0] ?? "";
    expect(switchTag).toMatch(/class="[^"]*\bpeer\b/);
    expect(labelTag).toContain("peer-disabled:opacity-70");
    expect(html.indexOf(switchTag)).toBeLessThan(html.indexOf(labelTag));

    // And the switch really is disabled in the states the label has to follow.
    expect(
      isDisabled(render({ loading: true, exportLogo: null, heightMm: null }), "switch"),
    ).toBe(true);
    expect(isDisabled(render({ saving: true }), "switch")).toBe(true);
  });

  // The markup of the first element whose opening tag carries `className`, balanced over
  // nested divs, so a test can ask what lies inside it.
  function elementWithClass(html: string, className: string) {
    const start = html.search(new RegExp(`<div[^>]*class="[^"]*\\b${className}\\b`));
    if (start === -1) return "";
    let depth = 0;
    const tags = /<(\/?)div\b/g;
    tags.lastIndex = start;
    for (let m = tags.exec(html); m; m = tags.exec(html)) {
      depth += m[1] ? -1 : 1;
      if (depth === 0) return html.slice(start, html.indexOf(">", m.index) + 1);
    }
    return "";
  }

  it("caps the slider and its label row together, at the full width on a narrow screen", () => {
    const html = render({ heightMm: 20 });

    const capped = elementWithClass(html, "max-w-sm");
    expect(capped).not.toBe("");
    // Both the label row (with the value) and the slider are inside the one wrapper...
    expect(capped).toContain("Logo height, in mm");
    expect(capped).toContain('data-testid="logo-height-value"');
    expect(capped).toContain('role="slider"');
    // ...which fills the card where the card is narrower than the cap...
    const openingTag = capped.slice(0, capped.indexOf(">") + 1);
    expect(openingTag).toMatch(/\bw-full\b/);
    // ...and the switch row is not part of it.
    expect(capped).not.toContain('role="switch"');
    expect(capped).not.toContain("Insert organization logo");
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
