import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  addProjectFileTag,
  deleteProjectFile,
  downloadProjectFile,
  listFileTags,
  listProjectFiles,
  removeProjectFileTag,
  uploadProjectFile,
} from "@/api/projects";
import { SupportingDocumentsSectionView } from "@/components/projects/SupportingDocumentsSectionView";
import { useFileUpload } from "@/hooks/useFileUpload";
import { downloadBlob } from "@/lib/download";
import { projectFilesReducer } from "@/lib/projectFiles";
import type { FileTag, ProjectFile } from "@/types/file";

interface SupportingDocumentsSectionProps {
  projectId: string | null;
  /** Saves a new project first; resolves to its id, or null if the form is invalid. */
  ensureSaved: () => Promise<string | null>;
  readOnly: boolean;
}

function messageOf(failure: unknown, fallback: string): string {
  return failure instanceof ApiError || failure instanceof Error ? failure.message : fallback;
}

export function SupportingDocumentsSection({
  projectId,
  ensureSaved,
  readOnly,
}: SupportingDocumentsSectionProps) {
  const { t } = useTranslation(["projects"]);
  const [files, dispatch] = useReducer(projectFilesReducer, []);
  const [vocabulary, setVocabulary] = useState<FileTag[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectFile | null>(null);
  const [uploadingName, setUploadingName] = useState<string | null>(null);
  // The project an upload is currently going to, which can be one the upload itself just
  // saved, before the form's own project state has caught up.
  const uploadTarget = useRef<string | null>(null);

  const send = useCallback((file: File, onProgress: (percent: number) => void) => {
    const target = uploadTarget.current;
    if (!target) throw new Error("No project to upload to");
    return uploadProjectFile(target, file, onProgress);
  }, []);
  const { status, progress, error, upload } = useFileUpload(send);

  useEffect(() => {
    listFileTags()
      .then(setVocabulary)
      .catch(() => setVocabulary([]));
  }, []);

  const refresh = useCallback(async (id: string) => {
    try {
      dispatch({ type: "loaded", files: await listProjectFiles(id) });
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    if (!projectId) {
      dispatch({ type: "loaded", files: [] });
      return;
    }
    dispatch({ type: "loaded", files: [] });
    void refresh(projectId);
  }, [projectId, refresh]);

  // The reason for a rejection is shown under the button; the toast repeats it where it
  // can't be missed.
  useEffect(() => {
    if (status === "rejected" && error) toast.error(error);
  }, [status, error]);

  async function handleBrowse(file: File) {
    let target = projectId;
    if (!target) {
      target = await ensureSaved();
      if (!target) return;
    }
    uploadTarget.current = target;
    setUploadingName(file.name);
    const result = await upload(file);
    if (result) {
      dispatch({ type: "added", file: result });
      // Also fetched again: saving a new project makes the list load for it too, and the
      // fetched list is the one that must win over whatever that first load saw.
      void refresh(target);
      toast.success(t("{{name}} uploaded.", { name: result.original_filename }));
    }
  }

  async function handleDownload(file: ProjectFile) {
    try {
      const { blob } = await downloadProjectFile(file.file_id);
      downloadBlob(blob, file.original_filename);
    } catch (failure) {
      toast.error(messageOf(failure, t("Failed to download file.")));
    }
  }

  // Tag changes show at once and are undone one tag at a time if the server refuses,
  // after which the list is fetched again so the screen shows what is really stored.
  async function handleAddTag(file: ProjectFile, tag: FileTag) {
    if (!projectId) return;
    dispatch({ type: "tagAdded", fileId: file.file_id, tag });
    try {
      await addProjectFileTag(projectId, file.file_id, tag.id);
    } catch (failure) {
      dispatch({ type: "tagRemoved", fileId: file.file_id, tagId: tag.id });
      toast.error(messageOf(failure, t("Failed to update tags.")));
      void refresh(projectId);
    }
  }

  async function handleRemoveTag(file: ProjectFile, tag: FileTag) {
    if (!projectId) return;
    dispatch({ type: "tagRemoved", fileId: file.file_id, tagId: tag.id });
    try {
      await removeProjectFileTag(projectId, file.file_id, tag.id);
    } catch (failure) {
      dispatch({ type: "tagAdded", fileId: file.file_id, tag });
      toast.error(messageOf(failure, t("Failed to update tags.")));
      void refresh(projectId);
    }
  }

  async function handleDeleteConfirm() {
    const target = deleteTarget;
    setDeleteTarget(null);
    if (!target || !projectId) return;
    try {
      await deleteProjectFile(projectId, target.file_id);
      dispatch({ type: "removed", fileId: target.file_id });
      toast.success(t("{{name}} deleted.", { name: target.original_filename }));
    } catch (failure) {
      toast.error(messageOf(failure, t("Failed to delete file.")));
    }
  }

  return (
    <SupportingDocumentsSectionView
      files={files}
      vocabulary={vocabulary}
      loadFailed={loadFailed}
      readOnly={readOnly}
      upload={{ status, progress, error, fileName: uploadingName }}
      deleteTarget={deleteTarget}
      onBrowse={(file) => void handleBrowse(file)}
      onDownload={(file) => void handleDownload(file)}
      onAddTag={(file, tag) => void handleAddTag(file, tag)}
      onRemoveTag={(file, tag) => void handleRemoveTag(file, tag)}
      onDeleteRequest={setDeleteTarget}
      onDeleteCancel={() => setDeleteTarget(null)}
      onDeleteConfirm={() => void handleDeleteConfirm()}
    />
  );
}
