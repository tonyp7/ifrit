import { describe, expect, it } from "vitest";

import { canAccessNavItem, NAV_ITEMS } from "@/config/navigation";
import type { Role } from "@/types/user";

function visibleLabels(roles: Role[]): string[] {
  return NAV_ITEMS.filter((item) => canAccessNavItem(item, roles)).map((item) => item.label);
}

describe("navigation items per role", () => {
  it("shows a consultant only Timesheet", () => {
    expect(visibleLabels(["consultant"])).toEqual(["Timesheet"]);
  });

  it("shows a manager Timesheet, Reporting and Projects", () => {
    expect(visibleLabels(["manager"])).toEqual(["Timesheet", "Reporting", "Projects"]);
  });

  it("shows an administrator without manager Timesheet and Configuration only", () => {
    expect(visibleLabels(["administrator"])).toEqual(["Timesheet", "Configuration"]);
  });

  it("shows the union, in order, for combined roles", () => {
    expect(visibleLabels(["administrator", "manager"])).toEqual([
      "Timesheet",
      "Reporting",
      "Projects",
      "Configuration",
    ]);
  });

  it("gates Reporting and Projects behind manager only", () => {
    const required = (label: string) => NAV_ITEMS.find((item) => item.label === label)?.requiredRoles;
    expect(required("Reporting")).toEqual(["manager"]);
    expect(required("Projects")).toEqual(["manager"]);
  });
});

describe("navigation item shape", () => {
  it("has no Home item", () => {
    expect(NAV_ITEMS.map((item) => item.label)).not.toContain("Home");
  });

  it("links Timesheet to /, Reporting to /reporting and Configuration to /configuration", () => {
    const to = (label: string) => NAV_ITEMS.find((item) => item.label === label)?.to;
    expect(to("Timesheet")).toBe("/");
    expect(to("Reporting")).toBe("/reporting");
    expect(to("Configuration")).toBe("/configuration");
  });

  it("has no dropdown items: every item is a plain link", () => {
    expect(NAV_ITEMS.every((item) => !("children" in item))).toBe(true);
  });

  it("puts Timesheet first", () => {
    expect(NAV_ITEMS[0].label).toBe("Timesheet");
  });
});
