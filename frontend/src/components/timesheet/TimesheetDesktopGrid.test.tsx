import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../../public/locales/en/common.json";
import timesheet from "../../../public/locales/en/timesheet.json";
import { TimesheetDesktopGrid } from "@/components/timesheet/TimesheetDesktopGrid";
import type { PeriodType } from "@/types/timesheet";

function daysOf(count: number): Date[] {
  return Array.from({ length: count }, (_, i) => new Date(2026, 8, 1 + i));
}

// Renders the grid with one service line and no callbacks that matter. Only the
// markup is looked at: column widths are a layout result that needs a real browser
// (checked separately), so this pins the class contract that produces them.
function render(periodType: PeriodType, dayCount: number) {
  const i18n = createInstance();
  void i18n.use(initReactI18next).init({
    lng: "en",
    resources: { en: { common, timesheet } },
    defaultNS: "common",
    initAsync: false,
    interpolation: { escapeValue: false },
  });
  return renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>
      <TimesheetDesktopGrid
        periodType={periodType}
        days={daysOf(dayCount)}
        serviceLines={[
          {
            service_line_id: "sl1",
            service_line_name: "Engineer",
            project_id: "p1",
            project_name: "Project",
            user_id: "u1",
          },
        ]}
        entries={{}}
        dayTotal={() => 0}
        serviceLineTotal={() => 0}
        periodTotal={0}
        periodLabel="September 2026"
        isUnassignedInPeriod={() => false}
        onCellChange={vi.fn()}
        onCellFocus={vi.fn()}
        onCellBlur={vi.fn()}
        onFocusDay={vi.fn()}
      />
    </I18nextProvider>,
  );
}

const tag = (html: string, pattern: RegExp) => pattern.exec(html)?.[0] ?? "";
const tableTag = (html: string) => tag(html, /<table[^>]*>/);
const wrapperTag = (html: string) => tag(html, /<div[^>]*overflow-x-auto[^>]*>/);
// The opening tag of the n-th header cell of the first header row (0 = "Timesheet").
// `<th` must be followed by a space or `>` so `<thead>` does not count as one.
const headerTag = (html: string, n: number) => html.match(/<th(?:\s[^>]*)?>/g)?.[n] ?? "";
const inputTag = (html: string) => tag(html, /<input[^>]*>/);

describe("TimesheetDesktopGrid in Month view", () => {
  it("uses a fixed layout so the day columns share the free width", () => {
    expect(tableTag(render("month", 30))).toContain("table-fixed");
  });

  it("never lets the table shrink below the first column, Total column and 36 px per day", () => {
    const style = (days: number) => tableTag(render("month", days));

    expect(style(31)).toContain("var(--grid-first)");
    expect(style(31)).toContain("4rem");
    expect(style(31)).toContain("31 * 2.25rem");
    expect(style(28)).toContain("28 * 2.25rem");
  });

  it("gives the day columns no fixed 48 px floor of their own", () => {
    const html = render("month", 30);

    // header 0 is "Timesheet", the last is "Total": the ones between are the days.
    expect(headerTag(html, 1)).not.toContain("min-w-12");
    expect(headerTag(html, 15)).not.toContain("min-w-12");
  });

  it("narrows the first column below a 1600 px window from one shared variable", () => {
    const html = render("month", 30);

    expect(wrapperTag(html)).toContain("[--grid-first:11rem]");
    expect(wrapperTag(html)).toContain("min-[1600px]:[--grid-first:13rem]");
    expect(headerTag(html, 0)).toContain("w-[var(--grid-first)]");
  });

  it("pins the Total column at 64 px", () => {
    const html = render("month", 30);

    // A whole class, not the tail of today's `min-w-16`.
    expect(headerTag(html, 31)).toMatch(/\sw-16[\s"]/);
  });

  it("uses tight horizontal padding in the day cells, inputs and headers", () => {
    const html = render("month", 30);

    expect(headerTag(html, 1)).toContain("px-1");
    expect(tag(html, /<td[^>]*text-center[^>]*px-0\.5[^>]*>/)).not.toBe("");
    // The input carries none of its own: the cell already keeps 2px per side.
    expect(inputTag(html)).toMatch(/\spx-0\s/);
    expect(inputTag(html)).not.toMatch(/\bp-1\b/);
  });

  it("keeps the bottom Total row's day cells as tight, so '12.5' fits", () => {
    const html = render("month", 30);
    const footer = html.slice(html.indexOf("<tfoot"));

    expect(footer).toContain("px-0.5");
  });
});

describe("TimesheetDesktopGrid in Week view", () => {
  it("is unchanged: automatic layout, its own column floors and padding", () => {
    const html = render("week", 7);

    expect(tableTag(html)).not.toContain("table-fixed");
    expect(tableTag(html)).not.toContain("min-width");
    expect(wrapperTag(html)).not.toContain("--grid-first");
    expect(headerTag(html, 1)).toContain("min-w-16");
    expect(headerTag(html, 0)).toContain("w-60");
    expect(inputTag(html)).toMatch(/\bp-1\b/);
  });
});
