import i18n from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { TimesheetHeader } from "@/components/timesheet/TimesheetHeader";

function render(periodTotal: number) {
  return renderToStaticMarkup(
    <TimesheetHeader
      periodType="week"
      periodDate={new Date(2026, 9, 14)}
      periodTotal={periodTotal}
      onPeriodTypeChange={vi.fn()}
      onNavigate={vi.fn()}
    />,
  );
}

describe("TimesheetHeader total", () => {
  it("reads 'Total: 7.5h' in English", () => {
    expect(render(7.5)).toContain("Total: 7.5h");
  });

  it("shows 0h for an empty period", () => {
    expect(render(0)).toContain("Total: 0h");
  });

  it("reads 'Total : 7,5 h' in French, with a no-break space before the colon and the unit", async () => {
    await i18n.changeLanguage("fr");
    const html = render(7.5);
    expect(html).toContain("Total : 7,5 h");
    expect(html).toContain("Semaine 42");
  });
});
