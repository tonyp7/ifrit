import { describe, expect, it } from "vitest";

import { seedReportGrid, seedTimesheetGrid } from "@/lib/timesheetGridSeed";
import { cellKey } from "@/lib/timesheetHours";
import type { TimeEntry, TimesheetReportRow } from "@/types/timesheet";

function entry(overrides: Partial<TimeEntry> = {}): TimeEntry {
  return {
    id: "e1",
    service_line_id: "sl1",
    service_line_name: "Build",
    project_id: "p1",
    project_name: "Alpha",
    date: "2026-10-05",
    hours: "7.50",
    is_locked: false,
    ...overrides,
  };
}

function row(overrides: Partial<TimesheetReportRow> = {}): TimesheetReportRow {
  return {
    user_id: "u1",
    full_name: "Ada Lovelace",
    project_id: "p1",
    project_name: "Alpha",
    project_status: "active",
    service_line_id: "sl1",
    service_line_name: "Build",
    entries: [],
    is_assigned: true,
    ...overrides,
  };
}

describe("seedTimesheetGrid", () => {
  it("is empty for no entries", () => {
    expect(seedTimesheetGrid([], "u1")).toEqual({ entries: {}, historicalServiceLines: [] });
  });

  it("keys each cell by owner, service line and day, with shortest-form hours", () => {
    const { entries } = seedTimesheetGrid(
      [entry({ hours: "7.50" }), entry({ date: "2026-10-06", hours: "8.00" })],
      "u1",
    );
    expect(entries[cellKey("u1", "sl1", "2026-10-05")]).toEqual({
      hours: "7.5",
      is_locked: false,
    });
    expect(entries[cellKey("u1", "sl1", "2026-10-06")]).toEqual({
      hours: "8",
      is_locked: false,
    });
  });

  it("carries the locked flag and shows zero hours as empty", () => {
    const { entries } = seedTimesheetGrid([entry({ hours: "0.00", is_locked: true })], "u1");
    expect(entries[cellKey("u1", "sl1", "2026-10-05")]).toEqual({
      hours: "",
      is_locked: true,
    });
  });

  it("lists a service line once, in first-seen order, owned by the row owner", () => {
    const { historicalServiceLines } = seedTimesheetGrid(
      [
        entry({ service_line_id: "slB", service_line_name: "Beta", project_name: "Alpha" }),
        entry({ service_line_id: "slA", service_line_name: "Alpha", date: "2026-10-05" }),
        entry({ service_line_id: "slB", service_line_name: "Beta", date: "2026-10-06" }),
      ],
      "u9",
    );
    expect(historicalServiceLines.map((l) => l.service_line_id)).toEqual(["slB", "slA"]);
    expect(historicalServiceLines.every((l) => l.user_id === "u9")).toBe(true);
    expect(historicalServiceLines[0]).toEqual({
      service_line_id: "slB",
      service_line_name: "Beta",
      project_id: "p1",
      project_name: "Alpha",
      user_id: "u9",
    });
  });
});

describe("seedReportGrid", () => {
  it("is empty for no rows", () => {
    expect(seedReportGrid([])).toEqual({
      entries: {},
      assignedByPair: {},
      projectStatusByPair: {},
    });
  });

  it("records assignment and project status per consultant and service line", () => {
    const { assignedByPair, projectStatusByPair } = seedReportGrid([
      row({
        user_id: "u1",
        service_line_id: "sl1",
        is_assigned: true,
        project_status: "active",
      }),
      row({
        user_id: "u2",
        service_line_id: "sl1",
        is_assigned: false,
        project_status: "draft",
      }),
    ]);
    expect(assignedByPair).toEqual({ u1__sl1: true, u2__sl1: false });
    expect(projectStatusByPair).toEqual({ u1__sl1: "active", u2__sl1: "draft" });
  });

  it("keys cells by each row's own consultant so two consultants never collide", () => {
    const { entries } = seedReportGrid([
      row({ user_id: "u1", entries: [entry({ hours: "4.00" })] }),
      row({ user_id: "u2", entries: [entry({ hours: "6.00", is_locked: true })] }),
    ]);
    expect(entries[cellKey("u1", "sl1", "2026-10-05")]).toEqual({
      hours: "4",
      is_locked: false,
    });
    expect(entries[cellKey("u2", "sl1", "2026-10-05")]).toEqual({
      hours: "6",
      is_locked: true,
    });
  });
});
