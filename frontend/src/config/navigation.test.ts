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

  it("shows a project_manager Timesheet then Reporting", () => {
    expect(visibleLabels(["project_manager"])).toEqual(["Timesheet", "Reporting"]);
  });

  it("shows a project_admin Timesheet and Projects but no Reporting", () => {
    expect(visibleLabels(["project_admin"])).toEqual(["Timesheet", "Projects"]);
  });

  it("shows an administrator without project_admin Timesheet and Configuration, not Projects", () => {
    expect(visibleLabels(["administrator"])).toEqual(["Timesheet", "Configuration"]);
  });

  it("shows the union, in order, for combined roles", () => {
    expect(visibleLabels(["administrator", "project_admin", "project_manager"])).toEqual([
      "Timesheet",
      "Reporting",
      "Projects",
      "Configuration",
    ]);
  });

  it("does not gate Reporting behind anything but project_manager", () => {
    const reporting = NAV_ITEMS.find((item) => item.label === "Reporting");
    expect(reporting?.requiredRoles).toEqual(["project_manager"]);
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
