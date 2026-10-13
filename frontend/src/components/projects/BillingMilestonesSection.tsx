import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { deleteBillingMilestone, reorderBillingMilestones } from "@/api/projects";
import { BillingMilestoneFormDialog } from "@/components/projects/BillingMilestoneFormDialog";
import { BillingMilestonesSectionView } from "@/components/projects/BillingMilestonesSectionView";
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
import {
  type MilestoneFormValues,
  milestoneToFormValues,
  reorderOptimistically,
} from "@/lib/billingMilestones";
import type { BillingMilestone } from "@/types/project";

interface BillingMilestonesSectionProps {
  /** null when the parent Project hasn't been saved yet. */
  projectId: string | null;
  milestones: BillingMilestone[];
  /** The project's contract value (sum of its service lines), the base of the %. */
  contractValue: string;
  minorUnit: number | null | undefined;
  onChanged: () => void;
  /** Validates + saves the parent Project form if it isn't saved yet, returning its id, or
   * null if validation failed (the form itself is already showing why). */
  ensureSaved: () => Promise<string | null>;
  /** true when the parent Project is `closed`: fully read-only. */
  readOnly: boolean;
}

export function BillingMilestonesSection({
  projectId,
  milestones,
  contractValue,
  minorUnit,
  onChanged,
  ensureSaved,
  readOnly,
}: BillingMilestonesSectionProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [dialogState, setDialogState] = useState<{
    projectId: string;
    milestoneId?: string;
    initialValues?: MilestoneFormValues;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BillingMilestone | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The list as shown: follows the project's saved list, but moves ahead of it during a
  // reorder so a drop lands at once instead of after the round trip. Re-synced while
  // rendering whenever the parent hands over a new list.
  const [shown, setShown] = useState(milestones);
  const [syncedFrom, setSyncedFrom] = useState(milestones);
  if (milestones !== syncedFrom) {
    setSyncedFrom(milestones);
    setShown(milestones);
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
      (ids) => reorderBillingMilestones(projectId, ids),
      setShown,
    )
      .then(onChanged)
      .catch((err: unknown) => {
        toast.error(
          err instanceof ApiError ? err.message : t("Failed to reorder billing milestones."),
        );
        // A 409 means the list changed elsewhere: reload it so the next drag starts from
        // what is actually stored.
        if (err instanceof ApiError && err.status === 409) onChanged();
      });
  }

  async function handleDelete() {
    if (!deleteTarget || !projectId) return;
    try {
      await deleteBillingMilestone(projectId, deleteTarget.id);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("Failed to delete billing milestone."),
      );
    }
  }

  return (
    <>
      <BillingMilestonesSectionView
        milestones={shown}
        contractValue={contractValue}
        minorUnit={minorUnit}
        readOnly={readOnly}
        error={error}
        onAdd={() => void handleAdd()}
        onEdit={(milestone) =>
          projectId &&
          setDialogState({
            projectId,
            milestoneId: milestone.id,
            initialValues: milestoneToFormValues(milestone, contractValue, minorUnit),
          })
        }
        onDuplicate={(milestone) =>
          projectId &&
          setDialogState({
            projectId,
            initialValues: milestoneToFormValues(milestone, contractValue, minorUnit),
          })
        }
        onDeleteRequest={setDeleteTarget}
        onReorder={handleReorder}
      />

      {dialogState && (
        <BillingMilestoneFormDialog
          open
          onOpenChange={(open) => !open && setDialogState(null)}
          projectId={dialogState.projectId}
          milestoneId={dialogState.milestoneId}
          initialValues={dialogState.initialValues}
          contractValue={contractValue}
          minorUnit={minorUnit}
          onSaved={onChanged}
        />
      )}

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Delete this billing milestone?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("This billing milestone will be permanently removed. This can't be undone.")}
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
