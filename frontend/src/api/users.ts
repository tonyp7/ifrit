import { apiClient } from "@/api/client";
import type { ThemePreference, User, UserInput, UserListResponse } from "@/types/user";

export function updateThemePreference(theme: ThemePreference) {
  return apiClient.patch<User>("/users/me/theme-preference", { theme_preference: theme });
}

export function listUsers(params: {
  role?: string;
  search?: string;
  page?: number;
  is_active?: boolean;
} = {}) {
  const query = new URLSearchParams();
  if (params.role) query.set("role", params.role);
  if (params.search) query.set("search", params.search);
  query.set("page", String(params.page ?? 1));
  if (params.is_active !== undefined) query.set("is_active", String(params.is_active));
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
