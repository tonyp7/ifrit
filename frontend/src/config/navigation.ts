import {
  CalendarClock,
  FileChartColumn,
  NotebookTabs,
  Receipt,
  Settings,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/types/user";

// Mirrors this app's role -> screen access rules: keep in sync with the actual
// role-gating logic (RequireRoles, backend endpoint role checks).
export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** undefined = every authenticated user, regardless of role. */
  requiredRoles?: Role[];
}

export const NAV_ITEMS: NavItem[] = [
  // The landing screen: every signed-in user has their own timesheet whatever roles
  // they hold, so this has no role list and is a plain link, never a dropdown.
  {
    to: "/",
    label: "Timesheet",
    icon: CalendarClock,
  },
  {
    to: "/reporting",
    label: "Reporting",
    icon: FileChartColumn,
    requiredRoles: ["manager"],
  },
  {
    to: "/projects",
    label: "Projects",
    icon: NotebookTabs,
    requiredRoles: ["manager"],
  },
  {
    to: "/invoices",
    label: "Invoices",
    icon: Receipt,
    requiredRoles: ["billing"],
  },
  {
    to: "/configuration",
    label: "Configuration",
    icon: Settings,
    requiredRoles: ["administrator"],
  },
];

export function canAccessNavItem(item: NavItem, roles: Role[]): boolean {
  return !item.requiredRoles || item.requiredRoles.some((role) => roles.includes(role));
}
