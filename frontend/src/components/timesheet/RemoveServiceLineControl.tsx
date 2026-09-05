import { X } from "lucide-react";
import { useState } from "react";
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
import { Button } from "@/components/ui/button";

interface RemoveServiceLineControlProps {
  /** Any entry (locked or not) for this line, for any day in the current period. */
  hasEntries: boolean;
  /** Any *locked* entry for this line, for any day in the current period. */
  hasLockedEntries: boolean;
  /** The entry owner is no longer currently assigned to this service line — see
   * docs/requirements/timesheet.md#persistence: read-only, same as locked. */
  isUnassigned?: boolean;
  /** e.g. "August 2026" or "Week 34" — same label the Shared Header shows. */
  periodLabel: string;
  /** No-dialog branch: no entries this period, purely a view-declutter action. */
  onRemove: () => void;
  /** Confirmed-destructive branch: clears every logged day this period, then
   * removes the line from view — unless the bulk clear came back partially
   * rejected (see TimesheetPage.tsx), in which case the line stays visible and
   * this component's own `hasLockedEntries` prop will reflect that on next render. */
  onConfirmedClear: () => Promise<void>;
}

// Three-way behavior per docs/requirements/timesheet.md#interactions--input-rules
// ("Removing a service line"): no entries this period -> immediate removal; logged
// (unlocked) entries this period -> confirm-then-clear; any locked entry this
// period -> disabled, no way to remove at all. Shared between
// TimesheetDesktopGrid and TimesheetMobileView so this branching and its
// AlertDialog aren't duplicated per breakpoint.
export function RemoveServiceLineControl({
  hasEntries,
  hasLockedEntries,
  isUnassigned = false,
  periodLabel,
  onRemove,
  onConfirmedClear,
}: RemoveServiceLineControlProps) {
  const { t } = useTranslation(["timesheet", "common"]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  async function handleConfirm() {
    setIsClearing(true);
    try {
      await onConfirmedClear();
      setConfirmOpen(false);
    } finally {
      setIsClearing(false);
    }
  }

  const disabled = hasLockedEntries || isUnassigned;
  const disabledReason = hasLockedEntries
    ? t("Can't remove — time logged for this period has been locked.")
    : isUnassigned
      ? t("Can't remove — this consultant is no longer assigned to this service line.")
      : undefined;

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={t("Remove service line")}
        disabled={disabled}
        // Native `title` rather than the Radix Tooltip component — this is the only
        // disabled-with-explanation control in the timesheet, not worth wiring up a
        // TooltipProvider for one button.
        title={disabledReason}
        onClick={() => (hasEntries ? setConfirmOpen(true) : onRemove())}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </Button>

      <AlertDialog
        open={confirmOpen}
        onOpenChange={(open) => !isClearing && setConfirmOpen(open)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Remove service line?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "This will delete any time logged for this service line for the period {{period}}. Are you sure you want to proceed?",
                { period: periodLabel },
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isClearing}>
              {t("Cancel", { ns: "common" })}
            </AlertDialogCancel>
            <AlertDialogAction disabled={isClearing} onClick={() => void handleConfirm()}>
              {t("Remove", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
