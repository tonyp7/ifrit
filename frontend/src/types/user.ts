export type Role = "administrator" | "project_admin" | "project_manager" | "consultant";

export type ThemePreference = "light" | "dark" | "system";

// Single source of truth for value -> display label — raw enum values are never
// shown to the user.
export const ROLE_LABELS: Record<Role, string> = {
  administrator: "Administrator",
  project_admin: "Project Admin",
  project_manager: "Project Manager",
  consultant: "Consultant",
};

export interface User {
  id: string;
  name_id: string;
  full_name: string;
  roles: Role[];
  is_sso: boolean;
  is_active: boolean;
  theme_preference: ThemePreference;
}

export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserInput {
  full_name: string;
  name_id: string;
  is_sso: boolean;
  roles: Role[];
  password?: string | null;
}
