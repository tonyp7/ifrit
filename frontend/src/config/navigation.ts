import { CalendarClock, Cog, House, NotebookTabs, type LucideIcon } from "lucide-react";

import type { Role } from "@/types/user";

export interface NavSubItem {
  to: string;
  label: string;
}

// Mirrors the Role -> Screen Access matrix in docs/requirements/user.md — keep in sync.
export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** undefined = every authenticated user, regardless of role. */
  requiredRoles?: Role[];
  /**
   * When present, the icon opens a dropdown of these destinations instead of
   * navigating to `to` directly — see docs/requirements/home.md#configuration-menu.
   * `to` is still used to derive the icon's active/highlighted state (any current
   * pathname under it counts as active).
   */
  children?: NavSubItem[];
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Home", icon: House },
  {
    to: "/timesheet",
    label: "Timesheet",
    icon: CalendarClock,
    requiredRoles: ["consultant", "manager", "administrator"],
  },
  {
    to: "/projects",
    label: "Projects",
    icon: NotebookTabs,
    requiredRoles: ["manager"],
  },
  {
    to: "/configuration",
    label: "Configuration",
    icon: Cog,
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
