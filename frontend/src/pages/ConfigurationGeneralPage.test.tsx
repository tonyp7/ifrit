import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it } from "vitest";

import common from "../../public/locales/en/common.json";
import configuration from "../../public/locales/en/configuration.json";
import { ConfigurationGeneralPage } from "@/pages/ConfigurationGeneralPage";

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
      <ConfigurationGeneralPage />
    </I18nextProvider>,
  );
}

describe("ConfigurationGeneralPage", () => {
  it("shows the PDF Report Export card below the Organization Logo card", () => {
    const html = render();

    const logoAt = html.indexOf("Organization Logo");
    const pdfAt = html.indexOf("PDF Report Export");
    expect(logoAt).toBeGreaterThan(-1);
    expect(pdfAt).toBeGreaterThan(logoAt);
  });

  it("shows the Information Banner card second, right below the Organization Logo card", () => {
    const html = render();

    const logoAt = html.indexOf("Organization Logo");
    const bannerAt = html.indexOf("Information Banner");
    expect(bannerAt).toBeGreaterThan(logoAt);
    expect(bannerAt).toBeLessThan(html.indexOf("PDF Report Export"));
  });

  it("shows the Standard Workday Length card fourth", () => {
    const html = render();

    expect(html.indexOf("Standard Workday Length")).toBeGreaterThan(
      html.indexOf("PDF Report Export"),
    );
    expect(html.indexOf("PDF Report Export")).toBeGreaterThan(
      html.indexOf("Information Banner"),
    );
  });
});
