import {
  CalendarClock,
  FileChartColumn,
  NotebookTabs,
  Settings,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/types/user";

export interface NavSubItem {
  to: string;
  label: string;
}

// Mirrors this app's role -> screen access rules: keep in sync with the actual
// role-gating logic (RequireRoles, backend endpoint role checks).
export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** undefined = every authenticated user, regardless of role. */
  requiredRoles?: Role[];
  /**
   * When present, the icon opens a dropdown of these destinations instead of
   * navigating to `to` directly. `to` is still used to derive the icon's
   * active/highlighted state (any current pathname under it counts as active).
   * Every child is shown to everyone who can see the item.
   */
  children?: NavSubItem[];
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
    children: [
      { to: "/configuration/companies", label: "Companies" },
      { to: "/configuration/users", label: "Users" },
    ],
  },
];

export function canAccessNavItem(item: NavItem, roles: Role[]): boolean {
  return !item.requiredRoles || item.requiredRoles.some((role) => roles.includes(role));
}
