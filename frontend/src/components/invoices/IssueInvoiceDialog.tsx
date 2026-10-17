import { useTranslation } from "react-i18next";

import { InvoiceWarnings } from "@/components/invoices/InvoiceWarnings";
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
import { Spinner } from "@/components/ui/spinner";
import { formatDueDate } from "@/lib/billingMilestones";
import { PAYMENT_TERMS_LABELS, type BlockingReason, type IssuePreview } from "@/types/invoice";

const BLOCKING_MESSAGES: Record<BlockingReason, string> = {
  project_not_active: "This invoice cannot be issued because its project is not Active.",
  no_lines: "An invoice needs at least one line.",
};

interface IssueInvoiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Null while it loads. */
  preview: IssuePreview | null;
  minorUnit: number | null;
  issuing: boolean;
  onConfirm: () => void;
}

/** The last look before issuing: the dates as plain dates, the number it should get, and
 * every warning. Issuing cannot be undone, only voided. */
export function IssueInvoiceDialog({
  open,
  onOpenChange,
  preview,
  minorUnit,
  issuing,
  onConfirm,
}: IssueInvoiceDialogProps) {
  const { t } = useTranslation(["invoices", "common"]);
  const blocked = !preview || preview.blocking.length > 0;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("Issue this invoice?")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t(
              "Once issued, the invoice is numbered and frozen. It can no longer be edited, only voided.",
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {preview && (
          <div className="flex flex-col gap-3 text-sm">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="text-muted-foreground">{t("Invoice date")}</dt>
              <dd>{formatDueDate(preview.invoice_date)}</dd>
              <dt className="text-muted-foreground">{t("Due date")}</dt>
              <dd>
                {preview.due_date ? formatDueDate(preview.due_date) : t("None")}
                {preview.payment_terms &&
                  ` (${t(PAYMENT_TERMS_LABELS[preview.payment_terms])})`}
              </dd>
              <dt className="text-muted-foreground">{t("Number")}</dt>
              <dd>
                <span className="font-mono">{preview.number}</span>{" "}
                <span className="text-muted-foreground">
                  {t("(unless another invoice is issued first)")}
                </span>
              </dd>
            </dl>
            {preview.blocking.map((reason) => (
              <p key={reason} className="text-destructive">
                {t(BLOCKING_MESSAGES[reason])}
              </p>
            ))}
            <InvoiceWarnings warnings={preview.warnings} omitted={[]} minorUnit={minorUnit} />
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={issuing}>
            {t("Cancel", { ns: "common" })}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={blocked || issuing}
            onClick={(event) => {
              // Stays open until the request ends, so a failure can be shown in place.
              event.preventDefault();
              onConfirm();
            }}
          >
            {issuing && <Spinner />}
            {issuing ? t("Issuing…") : t("Issue")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
