import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../public/locales/en/common.json";
import configuration from "../../public/locales/en/configuration.json";
import { ConfigurationInvoicesPage } from "@/pages/ConfigurationInvoicesPage";

// Requests never settle: the page is the cards as they are before anything has loaded.
vi.mock("@/api/invoiceTemplate", () => ({
  getInvoiceTemplate: vi.fn(() => new Promise(() => {})),
  getTemplateTokens: vi.fn(() => new Promise(() => {})),
  previewTemplate: vi.fn(),
  uploadTemplate: vi.fn(),
  resetTemplate: vi.fn(),
  downloadTemplate: vi.fn(),
  templateRejection: vi.fn(),
}));

function render() {
  const i18n = createInstance();
  void i18n.use(initReactI18next).init({
    lng: "en",
    resources: { en: { common, configuration } },
    defaultNS: "common",
    initAsync: false,
    interpolation: { escapeValue: false },
  });
  return renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>
      <ConfigurationInvoicesPage />
    </I18nextProvider>,
  );
}

describe("ConfigurationInvoicesPage", () => {
  it("shows Document Name, then Invoice Numbering, then Invoice Template", () => {
    const html = render();

    const name = html.indexOf("Document Name");
    const numbering = html.indexOf("Invoice Numbering");
    const template = html.indexOf("Invoice Template");
    expect(name).toBeGreaterThan(-1);
    expect(numbering).toBeGreaterThan(name);
    expect(template).toBeGreaterThan(numbering);
  });
});
