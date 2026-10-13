import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  ProjectReferencesSectionView,
  type ProjectReferencesSectionViewProps,
} from "@/components/projects/ProjectReferencesSectionView";
import { MAX_PROJECT_REFERENCES } from "@/lib/projectReferences";
import type { ProjectReference } from "@/types/project";

function reference(
  id: string,
  kind: ProjectReference["kind"],
  value: string,
  label: string | null = null,
): ProjectReference {
  return { id, project_id: "p", kind, label, value, position: 0 };
}

const three = [
  reference("a", "purchase_order", "4500123456"),
  reference("b", "contract", "C-9"),
  reference("c", "custom", "CC-77", "Cost center"),
];

const baseProps: ProjectReferencesSectionViewProps = {
  references: [],
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
function render(overrides: Partial<ProjectReferencesSectionViewProps> = {}) {
  return renderToStaticMarkup(<ProjectReferencesSectionView {...baseProps} {...overrides} />);
}

describe("ProjectReferencesSectionView", () => {
  it("shows only the title and Add without references", () => {
    const html = render();
    expect(html).toContain("Project References");
    expect(html).toContain("Add");
    expect(html).not.toContain("<table");
  });

  it("lists references in the given order with the Reference Name and Value columns", () => {
    const html = render({ references: three });
    expect(html).toContain("Reference Name");
    expect(html).toContain("Value");
    expect(html.indexOf("4500123456")).toBeLessThan(html.indexOf("C-9"));
    expect(html.indexOf("C-9")).toBeLessThan(html.indexOf("CC-77"));
  });

  it("names a typed reference by its kind and a custom one by its label", () => {
    const html = render({ references: three });
    expect(html).toContain("Purchase order");
    expect(html).toContain("Contract");
    expect(html).toContain("Cost center");
    expect(html).not.toContain(">Custom<");
  });

  it("offers a drag handle per row and an actions menu while editable", () => {
    const html = render({ references: three });
    expect(html.match(/Drag to reorder/g)).toHaveLength(3);
    expect(html.match(/Actions/g)).toHaveLength(3);
  });

  it("offers no drag handle with a single reference", () => {
    const html = render({ references: [three[0]] });
    expect(html).not.toContain("Drag to reorder");
    expect(html).toContain("Actions");
  });

  it("is listed only on a closed project: no Add, no handles, no menu", () => {
    const html = render({ references: three, readOnly: true });
    expect(html).toContain("4500123456");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("Drag to reorder");
    expect(html).not.toContain("Actions");
  });

  it("shows an error above the table", () => {
    const html = render({ references: three, error: "Failed to delete reference." });
    expect(html.indexOf("Failed to delete reference.")).toBeLessThan(html.indexOf("<table"));
  });

  it("disables Add at the limit and says why", () => {
    const many = Array.from({ length: MAX_PROJECT_REFERENCES }, (_, n) =>
      reference(`r${n}`, "purchase_order", `PO-${n}`),
    );
    const html = render({ references: many });
    expect(html).toContain(`Maximum of ${MAX_PROJECT_REFERENCES} references reached.`);
    const add = html.match(/<button[^>]*>(?:(?!<\/button>).)*Add<\/button>/);
    expect(add?.[0]).toContain("disabled");
  });
});
