import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it } from "vitest";

import common from "../../public/locales/en/common.json";
import { MineOnlySwitch } from "@/components/MineOnlySwitch";

function render(checked: boolean) {
  const i18n = createInstance();
  void i18n.use(initReactI18next).init({
    lng: "en",
    resources: { en: { common } },
    defaultNS: "common",
    initAsync: false,
  });
  return renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>
      <MineOnlySwitch checked={checked} onCheckedChange={() => {}} />
    </I18nextProvider>,
  );
}

describe("MineOnlySwitch", () => {
  it("is a labelled switch reflecting its state", () => {
    const html = render(true);
    expect(html).toContain('role="switch"');
    expect(html).toContain('aria-checked="true"');
    expect(html).toContain("Only see my projects");
    const id = /<button[^>]* id="([^"]+)"/.exec(html)?.[1];
    expect(html).toContain(`for="${id}"`);
  });

  it("shows off when unchecked", () => {
    expect(render(false)).toContain('aria-checked="false"');
  });
});
