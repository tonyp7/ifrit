import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { BillingMilestonesSectionView } from "@/components/projects/BillingMilestonesSectionView";
import type { BillingMilestone } from "@/types/project";

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

function milestone(id: string): BillingMilestone {
  return { id, project_id: "p", description: id, due_date: null, value: "1", position: 0 };
}

describe("BillingMilestonesSectionView sortable rows", () => {
  // Regression: the handle used to call useSortable for its row's id a second time. dnd-kit
  // keeps one registered node per id, written when a hook mounts, so a handle mounting after
  // its row (the first row, when a second milestone is added) replaced the row's node with an
  // empty one and that row could not be dragged until a reload.
  it("registers each milestone with dnd-kit exactly once", () => {
    sortableIds.length = 0;
    renderToStaticMarkup(
      <BillingMilestonesSectionView
        milestones={[milestone("a"), milestone("b"), milestone("c")]}
        contractValue="3"
        minorUnit={2}
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
