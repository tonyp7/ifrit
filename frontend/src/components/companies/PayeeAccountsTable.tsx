import { MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { deletePayeeAccount } from "@/api/companies";
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
import { PayeeAccountFormDialog } from "@/components/companies/PayeeAccountFormDialog";
import {
  formatAccountIdentifier,
  toPayeeAccountFormValues,
  type PayeeAccountFormValues,
} from "@/lib/payeeAccounts";
import { PAYMENT_MEANS_LABELS, type PayeeAccount } from "@/types/company";

export interface PayeeAccountsTableProps {
  /** null when the parent Company hasn't been saved yet. */
  companyId: string | null;
  accounts: PayeeAccount[];
  onChanged: () => void;
  /**
   * Validates + saves the parent Company form if it isn't saved yet, returning its
   * id (or the existing id if already saved). Returns null if validation fails:
   * the form itself will already be showing the error.
   */
  ensureSaved: () => Promise<string | null>;
}

export function PayeeAccountsTable({
  companyId,
  accounts,
  onChanged,
  ensureSaved,
}: PayeeAccountsTableProps) {
  const { t } = useTranslation(["company", "common"]);
  const [dialogState, setDialogState] = useState<{
    companyId: string;
    accountId?: string;
    initialValues?: PayeeAccountFormValues;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PayeeAccount | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAddClick() {
    const id = companyId ?? (await ensureSaved());
    if (!id) return;
    setDialogState({ companyId: id });
  }

  async function handleDelete() {
    if (!deleteTarget || !companyId) return;
    try {
      await deletePayeeAccount(companyId, deleteTarget.id);
      setDeleteTarget(null);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete payee account."));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t("Payee Accounts")}</h3>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void handleAddClick()}
        >
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("Add", { ns: "common" })}
        </Button>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("Payment means")}</TableHead>
              <TableHead>{t("Account")}</TableHead>
              <TableHead>{t("Currency")}</TableHead>
              <TableHead>{t("Bank")}</TableHead>
              <TableHead>{t("Primary")}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {accounts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground h-16 text-center">
                  {t("No payee accounts yet.")}
                </TableCell>
              </TableRow>
            ) : (
              accounts.map((account) => (
                <TableRow key={account.id}>
                  <TableCell>{t(PAYMENT_MEANS_LABELS[account.payment_means_code])}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    {formatAccountIdentifier(
                      account.account_scheme,
                      account.account_identifier,
                    )}
                  </TableCell>
                  <TableCell>{account.currency_code}</TableCell>
                  <TableCell>{account.bank_name ?? account.bic ?? "—"}</TableCell>
                  <TableCell>
                    {account.is_primary
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
                                accountId: account.id,
                                initialValues: toPayeeAccountFormValues(account),
                              })
                            }
                          >
                            {t("Edit", { ns: "common" })}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              companyId &&
                              setDialogState({
                                companyId,
                                initialValues: toPayeeAccountFormValues(account),
                              })
                            }
                          >
                            {t("Duplicate", { ns: "common" })}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => setDeleteTarget(account)}
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
        <PayeeAccountFormDialog
          open
          onOpenChange={(open) => !open && setDialogState(null)}
          companyId={dialogState.companyId}
          accountId={dialogState.accountId}
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
            <AlertDialogTitle>{t("Delete this payee account?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("{{value}} will be permanently removed. This can't be undone.", {
                value:
                  deleteTarget &&
                  formatAccountIdentifier(
                    deleteTarget.account_scheme,
                    deleteTarget.account_identifier,
                  ),
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
