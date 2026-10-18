import type { PaymentTerms } from "@/types/invoice";

function lastDayOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function plusDays(d: Date, days: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
}

/**
 * The due date a payment terms preset gives for an invoice dated `invoiceDate`, in calendar
 * days with no weekend or holiday adjustment. The server applies the same rule at issue,
 * from its own date; on a draft this is only an estimate "if issued today".
 */
export function dueDateFor(preset: PaymentTerms, invoiceDate: Date): Date {
  if (preset === "due_on_receipt") return plusDays(invoiceDate, 0);
  const [base, days] = preset.split("_") as [string, string | undefined];
  const offset = days ? Number(days) : 0;
  if (base === "net") return plusDays(invoiceDate, offset);
  return plusDays(lastDayOfMonth(invoiceDate), offset);
}
