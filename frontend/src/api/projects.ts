import { apiClient } from "@/api/client";
import type { FileTag, ProjectFile } from "@/types/file";
import type {
  BillingMilestone,
  BillingMilestoneInput,
  ProjectDetail,
  ProjectInput,
  ProjectListResponse,
  ServiceLine,
  ServiceLineInput,
  ProjectReference,
  ProjectReferenceInput,
} from "@/types/project";

export function listProjects(params: {
  search?: string;
  page?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  // "Only see my projects": always sent, the server's default is every project.
  mineOnly: boolean;
}) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  query.set("page", String(params.page ?? 1));
  query.set("mine_only", String(params.mineOnly));
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
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

export function addBillingMilestone(projectId: string, payload: BillingMilestoneInput) {
  return apiClient.post<BillingMilestone>(
    `/projects/${projectId}/billing-milestones`,
    payload,
  );
}

export function updateBillingMilestone(
  projectId: string,
  milestoneId: string,
  payload: BillingMilestoneInput,
) {
  return apiClient.patch<BillingMilestone>(
    `/projects/${projectId}/billing-milestones/${milestoneId}`,
    payload,
  );
}

export function deleteBillingMilestone(projectId: string, milestoneId: string) {
  return apiClient.delete<void>(`/projects/${projectId}/billing-milestones/${milestoneId}`);
}

/** Saves a new order: `ids` must be the project's complete milestone list, or the server
 * answers 409 (another session added or removed one). */
export function reorderBillingMilestones(projectId: string, ids: string[]) {
  return apiClient.patch<BillingMilestone[]>(
    `/projects/${projectId}/billing-milestones/order`,
    { ids },
  );
}

export function addProjectReference(projectId: string, payload: ProjectReferenceInput) {
  return apiClient.post<ProjectReference>(
    `/projects/${projectId}/project-references`,
    payload,
  );
}

export function updateProjectReference(
  projectId: string,
  referenceId: string,
  payload: ProjectReferenceInput,
) {
  return apiClient.patch<ProjectReference>(
    `/projects/${projectId}/project-references/${referenceId}`,
    payload,
  );
}

export function deleteProjectReference(projectId: string, referenceId: string) {
  return apiClient.delete<void>(`/projects/${projectId}/project-references/${referenceId}`);
}

/** Saves a new order: `ids` must be the project's complete reference list, or the server
 * answers 409 (another session added or removed one). */
export function reorderProjectReferences(projectId: string, ids: string[]) {
  return apiClient.patch<ProjectReference[]>(
    `/projects/${projectId}/project-references/order`,
    { ids },
  );
}

export function listProjectFiles(projectId: string) {
  return apiClient.get<ProjectFile[]>(`/projects/${projectId}/files`);
}

export function uploadProjectFile(
  projectId: string,
  file: File,
  onProgress?: (percent: number) => void,
) {
  const body = new FormData();
  body.append("file", file);
  return apiClient.upload<ProjectFile>(`/projects/${projectId}/files`, body, {
    method: "POST",
    onProgress,
  });
}

export function deleteProjectFile(projectId: string, fileId: string) {
  return apiClient.delete<void>(`/projects/${projectId}/files/${fileId}`);
}

// Adding a tag the file has, or removing one it lacks, succeeds without change, so the
// optimistic UI can fire these freely and retry after an error.
export function addProjectFileTag(projectId: string, fileId: string, tagId: string) {
  return apiClient.put<void>(`/projects/${projectId}/files/${fileId}/tags/${tagId}`);
}

export function removeProjectFileTag(projectId: string, fileId: string, tagId: string) {
  return apiClient.delete<void>(`/projects/${projectId}/files/${fileId}/tags/${tagId}`);
}

export function listFileTags() {
  return apiClient.get<FileTag[]>("/file-tags");
}

/** The file's bytes and the name to save them under. Fetched, never navigated to, so an
 * expired session refreshes and an error shows as a toast instead of replacing the app. */
export function downloadProjectFile(fileId: string) {
  return apiClient.getBlob(`/files/${fileId}/content`);
}
