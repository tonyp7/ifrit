import { apiClient } from "@/api/client";
import type { User } from "@/types/user";

export interface LoginPayload {
  email: string;
  password: string;
}

export function login(payload: LoginPayload) {
  return apiClient.post<User>("/auth/login", payload);
}

export function logout() {
  return apiClient.post<void>("/auth/logout");
}

export function fetchCurrentUser() {
  return apiClient.get<User>("/auth/me");
}
