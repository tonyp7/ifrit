import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import {
  addProjectFileTag,
  deleteProjectFile,
  downloadProjectFile,
  listFileTags,
  listProjectFiles,
  removeProjectFileTag,
  uploadProjectFile,
} from "@/api/projects";

vi.mock("@/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    upload: vi.fn(),
    getBlob: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

describe("project file API calls", () => {
  it("lists a project's files and the tag vocabulary", () => {
    void listProjectFiles("p1");
    void listFileTags();
    expect(apiClient.get).toHaveBeenCalledWith("/projects/p1/files");
    expect(apiClient.get).toHaveBeenCalledWith("/file-tags");
  });

  it("uploads as multipart form data under the field name `file`, with progress", () => {
    const onProgress = vi.fn();
    const file = new File(["%PDF"], "contract.pdf", { type: "application/pdf" });

    void uploadProjectFile("p1", file, onProgress);

    const [path, body, options] = vi.mocked(apiClient.upload).mock.calls[0];
    expect(path).toBe("/projects/p1/files");
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("file")).toBe(file);
    expect(options).toEqual({ method: "POST", onProgress });
  });

  it("deletes a file and adds and removes tags on the nested paths", () => {
    void deleteProjectFile("p1", "f1");
    void addProjectFileTag("p1", "f1", "t1");
    void removeProjectFileTag("p1", "f1", "t1");
    expect(apiClient.delete).toHaveBeenCalledWith("/projects/p1/files/f1");
    expect(apiClient.put).toHaveBeenCalledWith("/projects/p1/files/f1/tags/t1");
    expect(apiClient.delete).toHaveBeenCalledWith("/projects/p1/files/f1/tags/t1");
  });

  it("downloads through the authenticated blob request, never a bare link", () => {
    void downloadProjectFile("f1");
    expect(apiClient.getBlob).toHaveBeenCalledWith("/files/f1/content");
  });
});
