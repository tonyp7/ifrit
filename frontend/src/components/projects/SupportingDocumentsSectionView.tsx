import { Upload } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { ProjectFileRow } from "@/components/projects/ProjectFileRow";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { UploadStatus } from "@/hooks/useFileUpload";
import { KNOWN_FILE_EXTENSIONS } from "@/lib/fileIcons";
import type { FileTag, ProjectFile } from "@/types/file";

// What the file chooser offers. The server re-checks the real content, this only saves
// the user from picking something that is certain to be refused.
const ACCEPTED_TYPES = KNOWN_FILE_EXTENSIONS.map((extension) => `.${extension}`).join(",");

export interface SupportingDocumentsSectionViewProps {
  files: ProjectFile[];
  vocabulary: FileTag[];
  loadFailed: boolean;
  readOnly: boolean;
  upload: {
    status: UploadStatus;
    progress: number;
    error: string | null;
    fileName: string | null;
  };
  deleteTarget: ProjectFile | null;
  onBrowse: (file: File) => void;
  onDownload: (file: ProjectFile) => void;
  onAddTag: (file: ProjectFile, tag: FileTag) => void;
  onRemoveTag: (file: ProjectFile, tag: FileTag) => void;
  onDeleteRequest: (file: ProjectFile) => void;
  onDeleteCancel: () => void;
  onDeleteConfirm: () => void;
}

export function SupportingDocumentsSectionView({
  files,
  vocabulary,
  loadFailed,
  readOnly,
  upload,
  deleteTarget,
  onBrowse,
  onDownload,
  onAddTag,
  onRemoveTag,
  onDeleteRequest,
  onDeleteCancel,
  onDeleteConfirm,
}: SupportingDocumentsSectionViewProps) {
  const { t } = useTranslation(["projects", "common"]);
  const inputRef = useRef<HTMLInputElement>(null);
  const uploading = upload.status === "uploading";

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">{t("Supporting Documents")}</h3>

      {loadFailed && (
        <p className="text-destructive text-sm">{t("Failed to load documents.")}</p>
      )}

      {files.length > 0 && (
        <ul className="divide-y rounded-md border px-3">
          {files.map((file) => (
            <ProjectFileRow
              key={file.file_id}
              file={file}
              vocabulary={vocabulary}
              readOnly={readOnly}
              onDownload={onDownload}
              onDelete={onDeleteRequest}
              onAddTag={onAddTag}
              onRemoveTag={onRemoveTag}
            />
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-2">
        <div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="hidden"
            data-testid="project-file-input"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Cleared so choosing the same file again (after a failure) still fires.
              event.target.value = "";
              if (file) onBrowse(file);
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={readOnly || uploading}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-4 w-4" aria-hidden="true" />
            {t("Upload File...")}
          </Button>
        </div>

        {uploading && (
          <div className="flex flex-col gap-1">
            <p className="text-muted-foreground text-xs">
              {t("Uploading {{name}}…", { name: upload.fileName ?? "" })}
            </p>
            <Progress value={upload.progress} />
          </div>
        )}
        {(upload.status === "rejected" || upload.status === "error") && upload.error && (
          <p role="alert" className="text-destructive text-sm">
            {upload.error}
          </p>
        )}
      </div>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) onDeleteCancel();
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("Delete file {{name}}?", { name: deleteTarget?.original_filename ?? "" })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("The file and its tags will be permanently deleted from this project.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("Cancel", { ns: "common" })}</AlertDialogCancel>
            <AlertDialogAction onClick={onDeleteConfirm}>
              {t("Delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
