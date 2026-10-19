import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { InvoiceNumberingCardView } from "@/components/configuration/InvoiceNumberingCardView";
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
import { useInvoiceNumbering, type NumberingResult } from "@/hooks/useInvoiceNumbering";

export function InvoiceNumberingCard() {
  const { t } = useTranslation(["configuration", "common"]);
  const { state, editor, dispatchEditor, retry, saveFormat, saveNext } = useInvoiceNumbering();
  const [today] = useState(() => new Date());
  const [confirming, setConfirming] = useState(false);
  // What the user typed; null shows the server's next value.
  const [nextDraft, setNextDraft] = useState<string | null>(null);
  const [nextError, setNextError] = useState<string | null>(null);

  const networkMessage = t("The setting didn't save. Check your connection and try again.");

  async function save(confirm: boolean) {
    const result = await saveFormat(confirm);
    report(result, t("Invoice numbering applied"));
  }

  function report(result: NumberingResult, success: string) {
    if (result.ok) toast.success(success);
    else if (result.rejected) toast.error(result.message);
    else toast.error(networkMessage);
  }

  function handleSave() {
    // Once invoices have gone out, a new format is confirmed first: it only applies to
    // invoices issued from now on.
    if (state.saved?.has_issued) setConfirming(true);
    else void save(false);
  }

  async function handleSetNext() {
    const value = Number(nextDraft ?? state.saved?.next_value);
    const result = await saveNext(value);
    if (result.ok) {
      setNextDraft(null);
      setNextError(null);
      toast.success(t("Next number set"));
    } else if (result.rejected) {
      // Shown beside the field, which keeps the value for correcting it.
      setNextError(result.message);
    } else {
      toast.error(networkMessage);
    }
  }

  return (
    <>
      <InvoiceNumberingCardView
        loading={state.load === "loading"}
        loadFailed={state.load === "failed"}
        saved={state.saved}
        editor={editor}
        dispatch={dispatchEditor}
        busy={state.busy}
        today={today}
        onSave={handleSave}
        onRetry={retry}
        nextNumber={nextDraft ?? (state.saved ? String(state.saved.next_value) : "")}
        onNextNumberChange={(value) => {
          setNextDraft(value);
          setNextError(null);
        }}
        onSetNext={() => void handleSetNext()}
        nextError={nextError}
      />
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Change the invoice numbering?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "The new numbering system will affect newly issued invoices. Already issued invoices will keep their numbering.",
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("Cancel", { ns: "common" })}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirming(false);
                void save(true);
              }}
            >
              {t("Apply numbering")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
