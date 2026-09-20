import { CalendarClock, House, NotebookTabs, Settings, type LucideIcon } from "lucide-react";

import type { Role } from "@/types/user";

export interface NavSubItem {
  to: string;
  label: string;
  /** undefined = visible to every user who can already see the parent item. */
  requiredRoles?: Role[];
}

// Mirrors this app's role -> screen access rules — keep in sync with the actual
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
   */
  children?: NavSubItem[];
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Home", icon: House },
  {
    to: "/timesheet",
    label: "Timesheet",
    icon: CalendarClock,
    // Every role gets at least the own-timesheet screen. `project_manager`
    // additionally gets the Reporting sub-destination. Only a
    // `child.requiredRoles`-visible count > 1 turns this into
    // an actual dropdown (see canAccessNavItem/NavBar) — everyone else falls through
    // to a plain direct link to `to`.
    requiredRoles: ["consultant", "project_admin", "project_manager", "administrator"],
    children: [
      { to: "/timesheet", label: "My timesheet" },
      { to: "/reporting", label: "Reporting", requiredRoles: ["project_manager"] },
    ],
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
