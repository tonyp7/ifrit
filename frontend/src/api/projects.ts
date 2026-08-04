import { apiClient } from "@/api/client";
import type {
  ProjectDetail,
  ProjectInput,
  ProjectListResponse,
  ServiceLine,
  ServiceLineInput,
} from "@/types/project";

export function listProjects(params: { search?: string; page?: number }) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  query.set("page", String(params.page ?? 1));
  return apiClient.get<ProjectListResponse>(`/projects?${query.toString()}`);
}

export function getProject(projectId: string) {
  return apiClient.get<ProjectDetail>(`/projects/${projectId}`);
}

export function createProject(payload: ProjectInput) {
  return apiClient.post<ProjectDetail>("/projects", payload);
}

export function updateProject(projectId: string, payload: ProjectInput) {
  return apiClient.patch<ProjectDetail>(`/projects/${projectId}`, payload);
}

export function duplicateProject(projectId: string) {
  return apiClient.post<ProjectDetail>(`/projects/${projectId}/duplicate`);
}

export function deactivateProject(projectId: string) {
  return apiClient.post<void>(`/projects/${projectId}/deactivate`);
}

export function addServiceLine(projectId: string, payload: ServiceLineInput) {
  return apiClient.post<ServiceLine>(`/projects/${projectId}/service-lines`, payload);
}

export function updateServiceLine(
  projectId: string,
  lineId: string,
  payload: ServiceLineInput,
) {
  return apiClient.patch<ServiceLine>(
    `/projects/${projectId}/service-lines/${lineId}`,
    payload,
  );
}

export function deleteServiceLine(projectId: string, lineId: string) {
  return apiClient.delete<void>(`/projects/${projectId}/service-lines/${lineId}`);
}
