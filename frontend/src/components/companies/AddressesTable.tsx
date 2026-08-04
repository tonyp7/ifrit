import { MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { deleteAddress } from "@/api/companies";
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
import { AddressFormDialog } from "@/components/companies/AddressFormDialog";
import { ADDRESS_TYPE_LABELS, type Address } from "@/types/company";

interface AddressesTableProps {
  /** null when the parent Company hasn't been saved yet. */
  companyId: string | null;
  addresses: Address[];
  onChanged: () => void;
  /**
   * Validates + saves the parent Company form if it isn't saved yet, returning its
   * id (or the existing id if already saved). Returns null if validation fails —
   * the form itself will already be showing the error.
   */
  ensureSaved: () => Promise<string | null>;
}

// Address's nullable fields (line2/line3/postal_zone/country_subdivision) don't line
// up with the form's string-or-undefined fields — map explicitly rather than
// spreading the entity.
function toFormValues(address: Address) {
  return {
    address_type: address.address_type,
    line1: address.line1,
    line2: address.line2 ?? "",
    line3: address.line3 ?? "",
    city: address.city,
    postal_zone: address.postal_zone ?? "",
    country_subdivision: address.country_subdivision ?? "",
    country_code: address.country_code,
    is_primary: address.is_primary,
  };
}

export function AddressesTable({
  companyId,
  addresses,
  onChanged,
  ensureSaved,
}: AddressesTableProps) {
  const { t } = useTranslation(["company", "common"]);
  const [dialogState, setDialogState] = useState<{
    companyId: string;
    addressId?: string;
    initialValues?: ReturnType<typeof toFormValues>;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Address | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAddClick() {
    const id = companyId ?? (await ensureSaved());
    if (!id) return;
    setDialogState({ companyId: id });
  }

  async function handleDelete() {
    if (!deleteTarget || !companyId) return;
    try {
      await deleteAddress(companyId, deleteTarget.id);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete address."));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t("Addresses")}</h3>
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
              <TableHead>{t("Address")}</TableHead>
              <TableHead>{t("City")}</TableHead>
              <TableHead>{t("Country")}</TableHead>
              <TableHead>{t("Primary")}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {addresses.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-16 text-center text-muted-foreground">
                  {t("No addresses yet.")}
                </TableCell>
              </TableRow>
            ) : (
              addresses.map((address) => (
                <TableRow key={address.id}>
                  <TableCell>{t(ADDRESS_TYPE_LABELS[address.address_type])}</TableCell>
                  <TableCell>{address.line1}</TableCell>
                  <TableCell>{address.city}</TableCell>
                  <TableCell>{address.country_code}</TableCell>
                  <TableCell>
                    {address.is_primary
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
                                addressId: address.id,
                                initialValues: toFormValues(address),
                              })
                            }
                          >
                            {t("Edit", { ns: "common" })}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              companyId &&
                              setDialogState({ companyId, initialValues: toFormValues(address) })
                            }
                          >
                            {t("Duplicate", { ns: "common" })}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => setDeleteTarget(address)}
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
        <AddressFormDialog
          open
          onOpenChange={(open) => !open && setDialogState(null)}
          companyId={dialogState.companyId}
          addressId={dialogState.addressId}
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
            <AlertDialogTitle>{t("Delete this address?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("{{value}} will be permanently removed. This can't be undone.", {
                value: deleteTarget?.line1,
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
