import { useTranslation } from "react-i18next";

import { DueDatePicker } from "@/components/projects/DueDatePicker";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDueDate } from "@/lib/billingMilestones";
import { dueDateFor } from "@/lib/paymentTerms";
import { toDayKey } from "@/lib/timesheetDates";
import { PAYMENT_TERMS, PAYMENT_TERMS_LABELS, type PaymentTerms } from "@/types/invoice";

// Radix Select has no empty value: "none" stands for no preset.
const NONE = "none";

interface PaymentTermsFieldProps {
  paymentTerms: PaymentTerms | null;
  dueDate: string | null;
  /** Picking one clears the other: a draft has a preset or a fixed date, never both. */
  onChange: (value: { paymentTerms: PaymentTerms | null; dueDate: string | null }) => void;
  /** Today, for the estimate shown under a preset. */
  today: Date;
  disabled?: boolean;
}

export function PaymentTermsField({
  paymentTerms,
  dueDate,
  onChange,
  today,
  disabled,
}: PaymentTermsFieldProps) {
  const { t } = useTranslation(["invoices"]);

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="payment_terms">{t("Payment terms")}</Label>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Select
          value={paymentTerms ?? NONE}
          disabled={disabled}
          onValueChange={(value) =>
            onChange({
              paymentTerms: value === NONE ? null : (value as PaymentTerms),
              dueDate: null,
            })
          }
        >
          <SelectTrigger id="payment_terms">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>{t("No preset")}</SelectItem>
            {PAYMENT_TERMS.map((preset) => (
              <SelectItem key={preset} value={preset}>
                {t(PAYMENT_TERMS_LABELS[preset])}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {disabled ? (
          <p className="text-sm">{dueDate ? formatDueDate(dueDate) : ""}</p>
        ) : (
          <DueDatePicker
            id="due_date"
            value={dueDate}
            onChange={(value) => onChange({ paymentTerms: null, dueDate: value })}
          />
        )}
      </div>
      {paymentTerms ? (
        <p className="text-muted-foreground text-sm" data-testid="due-estimate">
          {t("Calculated when the invoice is issued. If issued today: {{date}}.", {
            date: formatDueDate(toDayKey(dueDateFor(paymentTerms, today))),
          })}
        </p>
      ) : dueDate ? (
        <p className="text-muted-foreground text-sm">{t("Fixed date")}</p>
      ) : (
        <p className="text-muted-foreground text-sm">{t("No due date")}</p>
      )}
    </div>
  );
}
