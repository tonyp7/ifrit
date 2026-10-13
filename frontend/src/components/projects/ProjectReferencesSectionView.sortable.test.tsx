import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ProjectReferencesSectionView } from "@/components/projects/ProjectReferencesSectionView";
import type { ProjectReference } from "@/types/project";

// Spies on dnd-kit's real `useSortable` to record which ids register.
const sortableIds = vi.hoisted(() => [] as string[]);
vi.mock("@dnd-kit/sortable", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@dnd-kit/sortable")>();
  return {
    ...actual,
    useSortable: (args: Parameters<typeof actual.useSortable>[0]) => {
      sortableIds.push(String(args.id));
      return actual.useSortable(args);
    },
  };
});

function reference(id: string): ProjectReference {
  return {
    id,
    project_id: "p",
    kind: "purchase_order",
    label: null,
    value: id,
    position: 0,
  };
}

describe("ProjectReferencesSectionView sortable rows", () => {
  // The same regression the milestones table guards: a row registered with dnd-kit twice
  // (once by its handle) cannot be dragged after a second row is added.
  it("registers each reference with dnd-kit exactly once", () => {
    sortableIds.length = 0;
    renderToStaticMarkup(
      <ProjectReferencesSectionView
        references={[reference("a"), reference("b"), reference("c")]}
        readOnly={false}
        error={null}
        onAdd={vi.fn()}
        onEdit={vi.fn()}
        onDuplicate={vi.fn()}
        onDeleteRequest={vi.fn()}
        onReorder={vi.fn()}
      />,
    );
    expect(sortableIds).toEqual(["a", "b", "c"]);
  });
});
