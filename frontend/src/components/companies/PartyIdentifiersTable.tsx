import { MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { deleteIdentifier } from "@/api/companies";
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
import { IdentifierFormDialog } from "@/components/companies/IdentifierFormDialog";
import { ID_TYPE_LABELS, type PartyIdentifier } from "@/types/company";

interface PartyIdentifiersTableProps {
  /** null when the parent Company hasn't been saved yet. */
  companyId: string | null;
  identifiers: PartyIdentifier[];
  onChanged: () => void;
  /**
   * Validates + saves the parent Company form if it isn't saved yet, returning its
   * id (or the existing id if already saved). Returns null if validation fails:
   * the form itself will already be showing the error.
   */
  ensureSaved: () => Promise<string | null>;
}

// PartyIdentifier's nullable fields (scheme_id) don't line up with the form's
// string-or-undefined fields: map explicitly rather than spreading the entity.
function toFormValues(identifier: PartyIdentifier) {
  return {
    id_type: identifier.id_type,
    scheme_id: identifier.scheme_id ?? "",
    id_value: identifier.id_value,
    is_primary: identifier.is_primary,
  };
}

export function PartyIdentifiersTable({
  companyId,
  identifiers,
  onChanged,
  ensureSaved,
}: PartyIdentifiersTableProps) {
  const { t } = useTranslation(["company", "common"]);
  const [dialogState, setDialogState] = useState<{
    companyId: string;
    identifierId?: string;
    initialValues?: ReturnType<typeof toFormValues>;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PartyIdentifier | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAddClick() {
    const id = companyId ?? (await ensureSaved());
    if (!id) return;
    setDialogState({ companyId: id });
  }

  async function handleDelete() {
    if (!deleteTarget || !companyId) return;
    try {
      await deleteIdentifier(companyId, deleteTarget.id);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete identifier."));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t("Party Identifiers")}</h3>
        <Button type="button" size="sm" variant="outline" onClick={() => void handleAddClick()}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("Add", { ns: "common" })}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("Type")}</TableHead>
              <TableHead>{t("Scheme")}</TableHead>
              <TableHead>{t("Value")}</TableHead>
              <TableHead>{t("Primary")}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {identifiers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-16 text-center text-muted-foreground">
                  {t("No identifiers yet.")}
                </TableCell>
              </TableRow>
            ) : (
              identifiers.map((identifier) => (
                <TableRow key={identifier.id}>
                  <TableCell>{t(ID_TYPE_LABELS[identifier.id_type])}</TableCell>
                  <TableCell>{identifier.scheme_id ?? "—"}</TableCell>
                  <TableCell>{identifier.id_value}</TableCell>
                  <TableCell>
                    {identifier.is_primary
                      ? t("Yes", { ns: "common" })
                      : t("No", { ns: "common" })}
                  </TableCell>
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
                              companyId &&
                              setDialogState({
                                companyId,
                                identifierId: identifier.id,
                                initialValues: toFormValues(identifier),
                              })
                            }
                          >
                            {t("Edit", { ns: "common" })}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              companyId &&
                              setDialogState({ companyId, initialValues: toFormValues(identifier) })
                            }
                          >
                            {t("Duplicate", { ns: "common" })}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => setDeleteTarget(identifier)}
                          >
                            {t("Delete", { ns: "common" })}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {dialogState && (
        <IdentifierFormDialog
          open
          onOpenChange={(open) => !open && setDialogState(null)}
          companyId={dialogState.companyId}
          identifierId={dialogState.identifierId}
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
            <AlertDialogTitle>{t("Delete this identifier?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("{{value}} will be permanently removed. This can't be undone.", {
                value: deleteTarget?.id_value,
              })}
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
