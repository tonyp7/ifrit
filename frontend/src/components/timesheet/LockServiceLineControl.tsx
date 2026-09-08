import { Lock, LockOpen } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

interface LockServiceLineControlProps {
  /** Every day in the current period is already locked for this line — the icon
   * represents the action (lock vs. unlock), not the current per-day mix. */
  isFullyLocked: boolean;
  onToggle: () => Promise<void>;
}

// Left of RemoveServiceLineControl's "x" — no confirmation dialog: a single click
// locks/unlocks the whole displayed period for this service line at once.
export function LockServiceLineControl({ isFullyLocked, onToggle }: LockServiceLineControlProps) {
  const { t } = useTranslation(["timesheet"]);
  const [isToggling, setIsToggling] = useState(false);

  async function handleClick() {
    setIsToggling(true);
    try {
      await onToggle();
    } finally {
      setIsToggling(false);
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={isFullyLocked ? t("Unlock service line") : t("Lock service line")}
      title={isFullyLocked ? t("Unlock service line") : t("Lock service line")}
      disabled={isToggling}
      onClick={() => void handleClick()}
    >
      {isFullyLocked ? (
        <LockOpen className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Lock className="h-4 w-4" aria-hidden="true" />
      )}
    </Button>
  );
}
