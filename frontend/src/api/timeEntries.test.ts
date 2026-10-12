import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import {
  exportTimesheetReport,
  getReportFilters,
  getTimesheetReport,
} from "@/api/timeEntries";

vi.mock("@/api/client", () => ({
  apiClient: { get: vi.fn(), getBlob: vi.fn() },
}));

beforeEach(() => vi.clearAllMocks());

const period = { startDate: "2026-08-01", endDate: "2026-08-31" };

describe("report API calls send the 'Only see my projects' switch", () => {
  it("asks the filter options for either scope", () => {
    void getReportFilters(true);
    void getReportFilters(false);
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      "/time-entries/report/filters?mine_only=true",
    );
    expect(apiClient.get).toHaveBeenNthCalledWith(
      2,
      "/time-entries/report/filters?mine_only=false",
    );
  });

  it("sends mine_only with the report rows", () => {
    void getTimesheetReport({ ...period, mineOnly: false, projectIds: ["p1"] });
    const [url] = vi.mocked(apiClient.get).mock.calls[0];
    const query = new URL(url, "http://x").searchParams;
    expect(query.get("mine_only")).toBe("false");
    expect(query.getAll("project_ids")).toEqual(["p1"]);
  });

  it("sends the same mine_only with an export, so it matches the screen", () => {
    void exportTimesheetReport("csv", { ...period, periodType: "month", mineOnly: true });
    const [url] = vi.mocked(apiClient.getBlob).mock.calls[0];
    expect(url.startsWith("/time-entries/report/export?")).toBe(true);
    const query = new URL(url, "http://x").searchParams;
    expect(query.get("format")).toBe("csv");
    expect(query.get("period_type")).toBe("month");
    expect(query.get("mine_only")).toBe("true");
  });
});
