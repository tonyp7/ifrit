import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  BillingMilestonesSectionView,
  type BillingMilestonesSectionViewProps,
} from "@/components/projects/BillingMilestonesSectionView";
import type { BillingMilestone } from "@/types/project";

function milestone(
  id: string,
  description: string,
  value: string,
  due_date: string | null = null,
): BillingMilestone {
  return { id, project_id: "p", description, due_date, value, position: 0 };
}

const three = [
  milestone("a", "Kick-off", "21600.0000", "2027-01-15"),
  milestone("b", "Delivery", "28800.0000"),
  milestone("c", "Acceptance", "14400.0000"),
];

const baseProps: BillingMilestonesSectionViewProps = {
  milestones: [],
  contractValue: "72000.0000",
  minorUnit: 2,
  readOnly: false,
  error: null,
  onAdd: vi.fn(),
  onEdit: vi.fn(),
  onDuplicate: vi.fn(),
  onDeleteRequest: vi.fn(),
  onReorder: vi.fn(),
};

// Rendered with the global English i18n instance (src/test/setup.ts), which fails the test
// on any key missing from public/locales/en.
function render(overrides: Partial<BillingMilestonesSectionViewProps> = {}) {
  return renderToStaticMarkup(<BillingMilestonesSectionView {...baseProps} {...overrides} />);
}

const WARNING = "The sum of all billing milestones differs from the contract value.";

describe("BillingMilestonesSectionView", () => {
  it("shows only the title and the add button without milestones", () => {
    const html = render();
    expect(html).toContain("Billing Milestones");
    expect(html).toContain("Add");
    expect(html).not.toContain("<table");
    expect(html).not.toContain(WARNING);
  });

  it("lists milestones in the given order with due date, % and value", () => {
    const html = render({ milestones: three });
    expect(html.indexOf("Kick-off")).toBeLessThan(html.indexOf("Delivery"));
    expect(html.indexOf("Delivery")).toBeLessThan(html.indexOf("Acceptance"));
    expect(html).toContain("30.00%");
    expect(html).toContain("40.00%");
    expect(html).toContain("21,600.00");
    expect(html).toContain(
      new Intl.DateTimeFormat(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date(2027, 0, 15)),
    );
  });

  it("totals the values and warns when they differ from the contract value", () => {
    const html = render({ milestones: three });
    expect(html).toContain("Total");
    expect(html).toContain("64,800.00");
    expect(html).toContain("90.00%");
    expect(html).toContain(WARNING);
  });

  it("does not warn when the milestones add up to the contract value", () => {
    const html = render({ milestones: three, contractValue: "64800.0000" });
    expect(html).not.toContain(WARNING);
  });

  it("shows — for the % when there is no contract value", () => {
    const html = render({ milestones: three, contractValue: "0.0000" });
    expect(html).not.toContain("%</td>");
    expect(html.match(/>—</g)?.length).toBe(4);
  });

  it("formats values at the currency's precision", () => {
    const html = render({
      milestones: [milestone("a", "Kick-off", "100.5000")],
      contractValue: "1000.0000",
      minorUnit: 0,
    });
    expect(html).toContain(">101<");
  });

  it("offers a drag handle per row only when there is something to reorder", () => {
    expect(render({ milestones: three }).match(/aria-label="Drag to reorder /g)).toHaveLength(
      3,
    );
    expect(render({ milestones: three })).toContain('aria-label="Drag to reorder Kick-off"');
    expect(render({ milestones: [three[0]] })).not.toContain("Drag to reorder");
  });

  it("is read-only on a closed project: no add, handles or row actions", () => {
    const html = render({ milestones: three, readOnly: true });
    expect(html).toContain("Kick-off");
    expect(html).not.toContain("Drag to reorder");
    expect(html).not.toContain(">Add<");
    expect(html).not.toContain("Actions");
  });
});
