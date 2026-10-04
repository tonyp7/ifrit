import { apiClient } from "@/api/client";
import type { StoredFileInfo } from "@/types/file";
import type { PdfExportSettings } from "@/types/settings";

export const ORG_LOGO_PATH = "/settings/org-logo";

/** Image URL for a stored file. A replaced logo gets a new file id, hence a new URL. */
export function fileContentUrl(fileId: string): string {
  return `/api/files/${fileId}/content`;
}

export function getOrgLogo() {
  return apiClient.get<StoredFileInfo>(ORG_LOGO_PATH);
}

export function uploadOrgLogo(file: File, onProgress?: (percent: number) => void) {
  const body = new FormData();
  body.append("file", file);
  return apiClient.upload<StoredFileInfo>(ORG_LOGO_PATH, body, { method: "PUT", onProgress });
}

export function deleteOrgLogo() {
  return apiClient.delete<void>(ORG_LOGO_PATH);
}

const PDF_EXPORT_PATH = "/settings/pdf-export";

export function getPdfExportSettings() {
  return apiClient.get<PdfExportSettings>(PDF_EXPORT_PATH);
}

/** Changes only the settings sent; the response is the whole updated group. */
export function patchPdfExportSettings(patch: Partial<PdfExportSettings>) {
  return apiClient.patch<PdfExportSettings>(PDF_EXPORT_PATH, patch);
}
