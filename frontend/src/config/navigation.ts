import {
  CalendarClock,
  FileChartColumn,
  NotebookTabs,
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
  // The landing screen: every role has at least its own timesheet, so this is
  // always shown and is a plain link, never a dropdown.
  {
    to: "/",
    label: "Timesheet",
    icon: CalendarClock,
    requiredRoles: ["consultant", "project_admin", "project_manager", "administrator"],
  },
  {
    to: "/reporting",
    label: "Reporting",
    icon: FileChartColumn,
    requiredRoles: ["project_manager"],
  },
  {
    to: "/projects",
    label: "Projects",
    icon: NotebookTabs,
    requiredRoles: ["project_admin"],
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
