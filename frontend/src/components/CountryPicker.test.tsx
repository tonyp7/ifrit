import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CountryPicker } from "@/components/CountryPicker";

// Rendered with the global English i18n instance (src/test/setup.ts), which fails the test
// on any key missing from public/locales/en. The open list is portalled, so only the closed
// field renders here; the list itself is covered by lib/countries tests and the live check.
function render(value: string) {
  return renderToStaticMarkup(<CountryPicker id="country" value={value} onChange={vi.fn()} />);
}

describe("CountryPicker", () => {
  it("shows a known country's flag and name", () => {
    const html = render("BE");
    expect(html).toContain('src="/flags/be.svg"');
    expect(html).toContain("Belgium");
    expect(html).toContain('id="country"');
    expect(html).toContain('role="combobox"');
  });

  it("shows an unknown stored code as is, with no flag", () => {
    const html = render("ZZ");
    expect(html).toContain(">ZZ<");
    expect(html).not.toContain("/flags/");
  });

  it("shows the placeholder when empty", () => {
    const html = render("");
    expect(html).toContain("Select a country…");
    expect(html).not.toContain("<img");
  });
});
