import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { deleteProjectReference, reorderProjectReferences } from "@/api/projects";
import { ProjectReferenceFormDialog } from "@/components/projects/ProjectReferenceFormDialog";
import { ProjectReferencesSectionView } from "@/components/projects/ProjectReferencesSectionView";
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
import { reorderOptimistically } from "@/lib/billingMilestones";
import { type ReferenceFormValues, referenceToFormValues } from "@/lib/projectReferences";
import type { ProjectReference } from "@/types/project";

interface ProjectReferencesSectionProps {
  /** null when the parent Project hasn't been saved yet. */
  projectId: string | null;
  references: ProjectReference[];
  onChanged: () => void;
  /** Validates + saves the parent Project form if it isn't saved yet, returning its id, or
   * null if validation failed (the form itself is already showing why). */
  ensureSaved: () => Promise<string | null>;
  /** true when the parent Project is `closed`: fully read-only. */
  readOnly: boolean;
}

export function ProjectReferencesSection({
  projectId,
  references,
  onChanged,
  ensureSaved,
  readOnly,
}: ProjectReferencesSectionProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [dialogState, setDialogState] = useState<{
    projectId: string;
    referenceId?: string;
    initialValues?: ReferenceFormValues;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectReference | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The list as shown: follows the project's saved list, but moves ahead of it during a
  // reorder so a drop lands at once instead of after the round trip. Re-synced while
  // rendering whenever the parent hands over a new list.
  const [shown, setShown] = useState(references);
  const [syncedFrom, setSyncedFrom] = useState(references);
  if (references !== syncedFrom) {
    setSyncedFrom(references);
    setShown(references);
  }

  async function handleAdd() {
    const id = projectId ?? (await ensureSaved());
    if (!id) return;
    setDialogState({ projectId: id });
  }

  function handleReorder(activeId: string, overId: string) {
    if (!projectId) return;
    reorderOptimistically(
      shown,
      activeId,
      overId,
      (ids) => reorderProjectReferences(projectId, ids),
      setShown,
    )
      .then(onChanged)
      .catch((err: unknown) => {
        toast.error(
          err instanceof ApiError ? err.message : t("Failed to reorder references."),
        );
        // A 409 means the list changed elsewhere: reload it so the next drag starts from
        // what is actually stored.
        if (err instanceof ApiError && err.status === 409) onChanged();
      });
  }

  async function handleDelete() {
    if (!deleteTarget || !projectId) return;
    try {
      await deleteProjectReference(projectId, deleteTarget.id);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete reference."));
    }
  }

  return (
    <>
      <ProjectReferencesSectionView
        references={shown}
        readOnly={readOnly}
        error={error}
        onAdd={() => void handleAdd()}
        onEdit={(reference) =>
          projectId &&
          setDialogState({
            projectId,
            referenceId: reference.id,
            initialValues: referenceToFormValues(reference),
          })
        }
        onDuplicate={(reference) =>
          projectId &&
          setDialogState({ projectId, initialValues: referenceToFormValues(reference) })
        }
        onDeleteRequest={setDeleteTarget}
        onReorder={handleReorder}
      />

      {dialogState && (
        <ProjectReferenceFormDialog
          open
          onOpenChange={(open) => !open && setDialogState(null)}
          projectId={dialogState.projectId}
          referenceId={dialogState.referenceId}
          initialValues={dialogState.initialValues}
          onSaved={onChanged}
        />
      )}

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Delete this reference?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("This reference will be permanently removed. This can't be undone.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("Cancel", { ns: "common" })}</AlertDialogCancel>
            <AlertDialogAction onClick={() => void handleDelete()}>
              {t("Delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
