import i18n from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Calendar } from "@/components/ui/calendar";

function render() {
  return renderToStaticMarkup(<Calendar mode="single" defaultMonth={new Date(2026, 9, 1)} />);
}

describe("Calendar", () => {
  it("names the month and weekdays in English", () => {
    const html = render();
    expect(html).toContain("October 2026");
    expect(html).toContain("Monday");
  });

  it("names the month, weekdays and labels in French, starting the week on Monday", async () => {
    await i18n.changeLanguage("fr");
    const html = render();
    expect(html).toContain("octobre 2026");
    expect(html).toContain("lundi");
    expect(html).not.toContain("October");
    // The first column header is Monday, not Sunday.
    expect(html.indexOf("lundi")).toBeLessThan(html.indexOf("dimanche"));
  });
});
