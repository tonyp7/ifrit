import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

interface VoidInvoiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  number: string;
  voiding: boolean;
  onConfirm: (reason: string) => void;
}

/** Cancels an issued invoice. It keeps its number and stays in the list; a void is not a
 * credit note. */
export function VoidInvoiceDialog({
  open,
  onOpenChange,
  number,
  voiding,
  onConfirm,
}: VoidInvoiceDialogProps) {
  const { t } = useTranslation(["invoices", "common"]);
  const reasonId = useId();
  const [reason, setReason] = useState("");
  // A fresh reason each time the dialog opens.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setReason("");
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("Void invoice {{number}}?", { number })}</AlertDialogTitle>
          <AlertDialogDescription>
            {t(
              "The invoice stays in the list with its number, marked void. This cannot be undone. To bill again, create a new invoice.",
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor={reasonId}>{t("Reason (optional)")}</Label>
          <Input
            id={reasonId}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={voiding}>
            {t("Cancel", { ns: "common" })}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={voiding}
            onClick={(event) => {
              event.preventDefault();
              onConfirm(reason);
            }}
          >
            {voiding && <Spinner />}
            {voiding ? t("Voiding…") : t("Void invoice")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
