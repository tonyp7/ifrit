import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { InformationBanner } from "@/components/InformationBanner";
import type { BannerColor, BannerIcon } from "@/types/settings";

function render(message: string, icon: BannerIcon = "info", color: BannerColor = "neutral") {
  return renderToStaticMarkup(
    <InformationBanner message={message} icon={icon} color={color} />,
  );
}

describe("InformationBanner", () => {
  it("shows the info icon before the message", () => {
    const html = render("Planned maintenance");

    expect(html).toContain("lucide-info");
    expect(html.indexOf("<svg")).toBeLessThan(html.indexOf("Planned maintenance"));
  });

  it("shows no icon for none", () => {
    expect(render("Planned maintenance", "none")).not.toContain("<svg");
  });

  it("shows a warning triangle in red", () => {
    const html = render("Careful", "warning", "red");

    expect(html).toContain("lucide-triangle-alert");
    expect(html).toContain("bg-red-50");
    expect(html).toContain("dark:bg-red-950");
  });

  it.each(["neutral", "blue", "yellow", "red"] as const)(
    "has a light and a dark style for %s",
    (color) => {
      const html = render("x", "info", color);
      expect(html).toMatch(color === "neutral" ? /bg-muted/ : /dark:bg-/);
    },
  );

  it("shows markup and links exactly as typed", () => {
    const html = render("<b>Soon</b> see https://example.com");

    expect(html).toContain("&lt;b&gt;Soon&lt;/b&gt; see https://example.com");
    expect(html).not.toContain("<b>");
    expect(html).not.toContain("<a ");
  });

  it("keeps line breaks and wraps long words", () => {
    const html = render("First\nSecond");

    expect(html).toContain("First\nSecond");
    expect(html).toContain("whitespace-pre-line");
    expect(html).toContain("overflow-wrap:anywhere");
  });

  it("is a polite status, not an alert, with the icon hidden from assistive technology", () => {
    const html = render("Hello");

    expect(html).toContain('role="status"');
    expect(html).not.toContain('role="alert"');
    expect(html).toContain('aria-hidden="true"');
  });
});
