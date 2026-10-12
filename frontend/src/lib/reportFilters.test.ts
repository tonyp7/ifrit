import { describe, expect, it } from "vitest";

import { pruneSelection } from "@/lib/reportFilters";
import type { TimesheetReportFilters } from "@/types/timesheet";

const mine: TimesheetReportFilters = {
  projects: [{ project_id: "A", name: "Alpha", status: "active" }],
  service_lines: [
    {
      service_line_id: "A1",
      service_line_name: "Build",
      project_id: "A",
      project_name: "Alpha",
    },
  ],
  consultants: [{ user_id: "u1", full_name: "Jane" }],
};

describe("pruneSelection", () => {
  it("drops projects, lines and consultants the new options no longer offer", () => {
    const pruned = pruneSelection(
      { projectIds: ["A", "C"], serviceLineIds: ["A1", "C1"], consultantIds: ["u1", "u9"] },
      mine,
    );
    expect(pruned).toEqual({
      projectIds: ["A"],
      serviceLineIds: ["A1"],
      consultantIds: ["u1"],
    });
  });

  it("returns the same arrays when everything is still offered", () => {
    const selection = { projectIds: ["A"], serviceLineIds: [], consultantIds: ["u1"] };
    const pruned = pruneSelection(selection, mine);
    expect(pruned.projectIds).toBe(selection.projectIds);
    expect(pruned.serviceLineIds).toBe(selection.serviceLineIds);
    expect(pruned.consultantIds).toBe(selection.consultantIds);
  });
});
