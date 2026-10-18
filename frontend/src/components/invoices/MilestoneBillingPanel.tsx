import { useTranslation } from "react-i18next";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { formatDueDate } from "@/lib/billingMilestones";
import { formatMoney } from "@/lib/format";
import type { ContextMilestone } from "@/types/invoice";

interface MilestoneBillingPanelProps {
  milestones: ContextMilestone[];
  selected: string[];
  onSelectedChange: (ids: string[]) => void;
  currencyCode: string;
  minorUnit: number | null;
  disabled?: boolean;
}

/** What to bill on a Fixed Price project: one or several of its billing milestones. Every
 * milestone is offered, already invoiced or not, since nothing records which ones have been
 * billed. */
export function MilestoneBillingPanel({
  milestones,
  selected,
  onSelectedChange,
  currencyCode,
  minorUnit,
  disabled,
}: MilestoneBillingPanelProps) {
  const { t } = useTranslation(["invoices"]);

  function toggle(id: string, checked: boolean) {
    onSelectedChange(
      checked ? [...selected, id] : selected.filter((selectedId) => selectedId !== id),
    );
  }

  return (
    <fieldset className="flex flex-col gap-2" disabled={disabled}>
      <legend className="mb-2 text-sm font-medium">{t("Billing milestones")}</legend>
      {milestones.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          {t(
            "This project has no billing milestones. A manager must add them on the project first.",
          )}
        </p>
      ) : (
        <div className="flex flex-col gap-3 sm:max-w-xl">
          {milestones.map((milestone) => (
            <div key={milestone.id} className="flex items-start gap-2">
              <Checkbox
                id={`milestone_${milestone.id}`}
                checked={selected.includes(milestone.id)}
                disabled={disabled}
                onCheckedChange={(checked) => toggle(milestone.id, checked === true)}
                className="mt-0.5"
              />
              <Label
                htmlFor={`milestone_${milestone.id}`}
                className="flex min-w-0 flex-1 items-start justify-between gap-4 font-normal"
              >
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="break-words">{milestone.description}</span>
                  {milestone.due_date && (
                    <span className="text-muted-foreground text-xs">
                      {t("Due {{date}}", { date: formatDueDate(milestone.due_date) })}
                    </span>
                  )}
                </span>
                <span className="shrink-0 tabular-nums">
                  {formatMoney(milestone.value, minorUnit)} {currencyCode}
                </span>
              </Label>
            </div>
          ))}
        </div>
      )}
    </fieldset>
  );
}
