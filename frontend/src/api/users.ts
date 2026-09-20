import { apiClient } from "@/api/client";
import type { ThemePreference, User, UserInput, UserListResponse } from "@/types/user";

export function updateThemePreference(theme: ThemePreference) {
  return apiClient.patch<User>("/users/me/theme-preference", { theme_preference: theme });
}

export function listUsers(params: {
  role?: string;
  search?: string;
  page?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
} = {}) {
  const query = new URLSearchParams();
  if (params.role) query.set("role", params.role);
  if (params.search) query.set("search", params.search);
  query.set("page", String(params.page ?? 1));
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
  return apiClient.get<UserListResponse>(`/users?${query.toString()}`);
}

export function getUser(userId: string) {
  return apiClient.get<User>(`/users/${userId}`);
}

export function createUser(payload: UserInput) {
  return apiClient.post<User>("/users", payload);
}

export function updateUser(userId: string, payload: UserInput) {
  return apiClient.patch<User>(`/users/${userId}`, payload);
}

export function deactivateUser(userId: string) {
  return apiClient.post<void>(`/users/${userId}/deactivate`);
}

export function resetPassword(userId: string, newPassword: string) {
  return apiClient.post<void>(`/users/${userId}/reset-password`, {
    new_password: newPassword,
  });
}
