import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../../public/locales/en/common.json";
import configuration from "../../../public/locales/en/configuration.json";
import {
  InvoiceTemplateCardView,
  type InvoiceTemplateCardViewProps,
} from "@/components/configuration/InvoiceTemplateCardView";
import type { InvoiceTemplateInfo, TemplateToken } from "@/types/invoiceTemplate";

const defaultInfo: InvoiceTemplateInfo = {
  source: "default",
  filename: "invoice-template.odt",
  size_bytes: 15316,
  uploaded_by_name: null,
  uploaded_at: null,
  placeholders: ["invoice_number"],
};

const customInfo: InvoiceTemplateInfo = {
  source: "custom",
  filename: "acme.odt",
  size_bytes: 20480,
  uploaded_by_name: "Sam Admin",
  uploaded_at: "2026-10-20T08:30:00Z",
  placeholders: ["invoice_number"],
};

const tokens: TemplateToken[] = [
  {
    name: "invoice_number",
    description: "The invoice number",
    kind: "value",
    optional_capable: true,
    example: "INV-2026-0043",
  },
  {
    name: "invoice_lines",
    description: "The line-items table",
    kind: "lines",
    optional_capable: false,
    example: "",
  },
];

const baseProps: InvoiceTemplateCardViewProps = {
  info: defaultInfo,
  loading: false,
  loadFailed: false,
  tokens,
  review: null,
  saving: false,
  resetting: false,
  downloading: false,
  onChooseFile: vi.fn(),
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
  onReset: vi.fn(),
  onDownload: vi.fn(),
};

// Real translations; a key the card uses that the locale files lack fails the test.
function render(overrides: Partial<InvoiceTemplateCardViewProps> = {}) {
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
      <InvoiceTemplateCardView {...baseProps} {...overrides} />
    </I18nextProvider>,
  );
  expect(missing).toEqual([]);
  return html;
}

/** The opening tag of the first button whose text is `label`. */
function button(html: string, label: string): string {
  const match = new RegExp(`<button[^>]*>(?:(?!</button>).)*${label}`, "s").exec(html);
  expect(match, `button ${label}`).not.toBeNull();
  return match![0];
}

describe("InvoiceTemplateCardView", () => {
  it("is titled Invoice Template", () => {
    expect(render()).toContain("Invoice Template");
  });

  it("says the default template is in use, with Download and a disabled Reset to default", () => {
    const html = render();

    expect(html).toContain("Default template");
    expect(button(html, "Download")).not.toContain('disabled=""');
    expect(button(html, "Reset to default")).toContain('disabled=""');
  });

  it("names an uploaded template, who uploaded it and when, and enables Reset to default", () => {
    const html = render({ info: customInfo });

    expect(html).toContain("acme.odt");
    expect(html).toContain("Uploaded by Sam Admin on");
    expect(html).not.toContain("Default template");
    expect(button(html, "Reset to default")).not.toContain('disabled=""');
  });

  it("offers Download whichever template is in use", () => {
    expect(render({ info: customInfo })).toContain("Download");
    expect(render({ info: defaultInfo })).toContain("Download");
  });

  it("has no Remove button: Reset to default is the only way back", () => {
    expect(render({ info: customInfo })).not.toContain(">Remove<");
  });

  it("only accepts .odt files in the chooser", () => {
    expect(render()).toContain('accept=".odt,application/vnd.oasis.opendocument.text"');
  });

  it("shows a message when the template cannot be loaded, and disables the actions", () => {
    const html = render({ info: null, loadFailed: true });

    expect(html).toContain("Couldn&#x27;t load the invoice template.");
    expect(button(html, "Upload…")).toContain('disabled=""');
  });

  it("disables the actions while the template in use is being read", () => {
    const html = render({ info: null, loading: true });

    expect(button(html, "Upload…")).toContain('disabled=""');
    expect(button(html, "Reset to default")).toContain('disabled=""');
  });

  describe("reviewing a chosen file", () => {
    it("shows that it is being checked and disables the actions", () => {
      const html = render({ review: { fileName: "new.odt", status: "checking" } });

      expect(html).toContain("new.odt");
      expect(html).toContain("Checking the template and making a sample PDF…");
      expect(button(html, "Upload…")).toContain('disabled=""');
      expect(html).not.toContain("Use this template");
    });

    it("shows the sample and asks for confirmation before anything changes", () => {
      const html = render({
        review: { fileName: "new.odt", status: "ready", pdfUrl: "blob:sample", warnings: [] },
      });

      expect(html).toContain('<iframe title="Sample invoice" src="blob:sample"');
      expect(html).toContain("Nothing changes until you confirm.");
      expect(html).toContain("Use this template");
      expect(html).toContain("Cancel");
      expect(html).toContain('href="blob:sample"');
    });

    it("lists the warnings of a valid file and still offers to use it", () => {
      const html = render({
        review: {
          fileName: "new.odt",
          status: "ready",
          pdfUrl: "blob:sample",
          warnings: [
            {
              part: "styles.xml",
              message: "This font is not installed and will be replaced",
              snippet: "Comic Sans",
            },
          ],
        },
      });

      expect(html).toContain("Warnings");
      expect(html).toContain("This font is not installed and will be replaced");
      expect(html).toContain("<code");
      expect(html).toContain("Comic Sans");
      expect(html).toContain("Use this template");
    });

    it("lists every problem of an invalid file and offers no confirmation", () => {
      const html = render({
        review: {
          fileName: "bad.odt",
          status: "rejected",
          warnings: [],
          problems: [
            { part: "content.xml", message: "Unknown placeholder", snippet: "{{nope}}" },
            { part: "Scripts/m.xml", message: "The file contains a macro", snippet: null },
          ],
        },
      });

      expect(html).toContain("This template cannot be used");
      expect(html).toContain("Unknown placeholder");
      expect(html).toContain("{{nope}}");
      expect(html).toContain("The file contains a macro");
      expect(html).not.toContain("Use this template");
      expect(html).not.toContain("<iframe");
      expect(html).toContain("Close");
    });

    it("shows why a file could not be checked, such as the engine being unavailable", () => {
      const html = render({
        review: {
          fileName: "new.odt",
          status: "failed",
          message: "The PDF engine is not available",
        },
      });

      expect(html).toContain("The PDF engine is not available");
      expect(html).not.toContain("Use this template");
    });

    it("shows that the upload is being saved", () => {
      const html = render({
        saving: true,
        review: { fileName: "new.odt", status: "ready", pdfUrl: "blob:sample", warnings: [] },
      });

      expect(button(html, "Use this template")).toContain('disabled=""');
    });
  });

  describe("the placeholder reference", () => {
    it("is collapsed by default and lists every placeholder with its meaning and example", () => {
      const html = render();

      expect(html).toContain("<details");
      expect(html).not.toContain("<details open");
      expect(html).toContain("{{invoice_number}}");
      expect(html).toContain("The invoice number");
      expect(html).toContain("INV-2026-0043");
      expect(html).toContain("{{invoice_lines}}");
    });

    it("explains the optional form with a question mark", () => {
      expect(render()).toContain("{{payee_bank_name?}}");
    });

    it("shows that it is loading until the placeholders arrive", () => {
      expect(render({ tokens: null })).toContain("Loading…");
    });
  });
});
