import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  WorkdayLengthCardView,
  type WorkdayLengthCardViewProps,
} from "@/components/configuration/WorkdayLengthCardView";

const baseProps: WorkdayLengthCardViewProps = {
  loading: false,
  loadFailed: false,
  seconds: 28800,
  saving: false,
  onCommit: vi.fn(),
  onRetry: vi.fn(),
};

function render(overrides: Partial<WorkdayLengthCardViewProps> = {}) {
  return renderToStaticMarkup(<WorkdayLengthCardView {...baseProps} {...overrides} />);
}

// value and disabled state of each number field, in order.
function fields(html: string): { value: string; disabled: boolean }[] {
  return [...html.matchAll(/<input[^>]*>/g)].map(([tag]) => ({
    value: /value="([^"]*)"/.exec(tag)?.[1] ?? "",
    disabled: /\sdisabled=""/.test(tag),
  }));
}

describe("WorkdayLengthCardView", () => {
  it("shows the saved length as hours, minutes and seconds", () => {
    const html = render();

    expect(html).toContain("Standard Workday Length");
    expect(html).toContain("Hours");
    expect(html).toContain("Minutes");
    expect(html).toContain("Seconds");
    expect(fields(html)).toEqual([
      { value: "8", disabled: false },
      { value: "0", disabled: false },
      { value: "0", disabled: false },
    ]);
  });

  it("allows 24 in the hours field so a full day can be shown", () => {
    const html = render({ seconds: 86400 });

    expect(fields(html)[0].value).toBe("24");
    expect(html).toMatch(/max="24"/);
  });

  it("shows empty, disabled fields while loading", () => {
    expect(fields(render({ loading: true, seconds: null }))).toEqual([
      { value: "", disabled: true },
      { value: "", disabled: true },
      { value: "", disabled: true },
    ]);
  });

  it("disables the fields while saving", () => {
    expect(fields(render({ saving: true })).every((field) => field.disabled)).toBe(true);
  });

  it("offers a retry after a failed load", () => {
    const html = render({ loadFailed: true, seconds: null });

    expect(html).toContain("Couldn&#x27;t load the workday length.");
    expect(html).toContain("Try again");
  });
});
