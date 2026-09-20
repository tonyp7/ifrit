import { ConsultantName } from "@/components/projects/ConsultantName";
import { MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { deleteServiceLine } from "@/api/projects";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ServiceLineFormDialog } from "@/components/projects/ServiceLineFormDialog";
import { formatMoney, formatQuantity } from "@/lib/format";
import { type ServiceLine, type ServiceLineConsultant, UOM_LABELS } from "@/types/project";

// ServiceLine's users are ServiceLineConsultant objects: map to bare ids for the
// form's user_ids field rather than spreading the entity.
function serviceLineToFormValues(line: ServiceLine) {
  return {
    name: line.name ?? "",
    quantity: line.quantity,
    uom: line.uom,
    unit_price: line.unit_price,
    user_ids: line.users.map((u) => u.id),
  };
}

interface ServiceLinesTableProps {
  /** null when the parent Project hasn't been saved yet. */
  projectId: string | null;
  serviceLines: ServiceLine[];
  onChanged: () => void;
  /**
   * Validates + saves the parent Project form if it isn't saved yet, returning its
   * id (or the existing id if already saved). Returns null if validation fails:
   * the form itself will already be showing the error.
   */
  ensureSaved: () => Promise<string | null>;
  /** true when the parent Project is `closed`: fully read-only, no add/edit/delete. */
  readOnly: boolean;
  /** The project's invoicing currency's decimal precision, for display formatting
   * (e.g. 2 for USD, 0 for JPY). */
  minorUnit: number | null | undefined;
}

export function ServiceLinesTable({
  projectId,
  serviceLines,
  onChanged,
  ensureSaved,
  readOnly,
  minorUnit,
}: ServiceLinesTableProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [dialogState, setDialogState] = useState<{
    projectId: string;
    serviceLineId?: string;
    initialValues?: ReturnType<typeof serviceLineToFormValues>;
    initialConsultants?: ServiceLineConsultant[];
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ServiceLine | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAddClick() {
    const id = projectId ?? (await ensureSaved());
    if (!id) return;
    setDialogState({ projectId: id });
  }

  async function handleDelete() {
    if (!deleteTarget || !projectId) return;
    try {
      await deleteServiceLine(projectId, deleteTarget.id);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete service line."));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t("Service Lines")}</h3>
        {!readOnly && (
          <Button type="button" size="sm" variant="outline" onClick={() => void handleAddClick()}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("Add", { ns: "common" })}
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("Name")}</TableHead>
              <TableHead>{t("Quantity")}</TableHead>
              <TableHead>{t("Unit")}</TableHead>
              <TableHead>{t("Unit price")}</TableHead>
              <TableHead>{t("Value")}</TableHead>
              <TableHead>{t("Consultants")}</TableHead>
              {!readOnly && <TableHead />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {serviceLines.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-16 text-center text-muted-foreground">
                  {t("No service lines yet.")}
                </TableCell>
              </TableRow>
            ) : (
              serviceLines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.name || "—"}</TableCell>
                  <TableCell>{formatQuantity(line.quantity)}</TableCell>
                  <TableCell>{t(UOM_LABELS[line.uom])}</TableCell>
                  <TableCell>{formatMoney(line.unit_price, minorUnit)}</TableCell>
                  <TableCell>{formatMoney(line.value, minorUnit)}</TableCell>
                  <TableCell>
                    {line.users.length > 0
                      ? line.users.map((u) => (
                          <div key={u.id}>
                            <ConsultantName consultant={u} />
                          </div>
                        ))
                      : "—"}
                  </TableCell>
                  {!readOnly && (
                    <TableCell>
                      <div className="flex justify-end">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                              <span className="sr-only">{t("Actions", { ns: "common" })}</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() =>
                                projectId &&
                                setDialogState({
                                  projectId,
                                  serviceLineId: line.id,
                                  initialValues: serviceLineToFormValues(line),
                                  initialConsultants: line.users,
                                })
                              }
                            >
                              {t("Edit", { ns: "common" })}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                projectId &&
                                setDialogState({
                                  projectId,
                                  initialValues: serviceLineToFormValues(line),
                                  initialConsultants: line.users,
                                })
                              }
                            >
                              {t("Duplicate", { ns: "common" })}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => setDeleteTarget(line)}
                            >
                              {t("Delete", { ns: "common" })}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {dialogState && (
        <ServiceLineFormDialog
          open
          onOpenChange={(open) => !open && setDialogState(null)}
          projectId={dialogState.projectId}
          serviceLineId={dialogState.serviceLineId}
          initialValues={dialogState.initialValues}
          initialConsultants={dialogState.initialConsultants}
          onSaved={onChanged}
          minorUnit={minorUnit}
        />
      )}

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Delete this service line?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("This service line will be permanently removed. This can't be undone.")}
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
    </div>
  );
}
