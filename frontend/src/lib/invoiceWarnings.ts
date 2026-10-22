import type { InvoiceWarning, InvoiceWarningCode } from "@/types/invoice";

// Warnings that depend only on what the form holds, worked out live as it changes, by the
// same rules the server uses on a saved invoice.
const FORM_CODES: InvoiceWarningCode[] = [
  "zero_quantity",
  "no_payee_account",
  "payee_currency",
  "tax_rate_not_derivable",
  "negative_subtotal",
  "no_due_date",
];

export function formWarnings(input: {
  quantities: string[];
  payeeCurrency: string | null;
  invoiceCurrency: string | null;
  /** The payment terms preset and the fixed due date: with neither, the invoice prints no due
   * date. Required, so a caller cannot forget them and silently lose the warning. */
  paymentTerms: string | null;
  dueDate: string | null;
  subtotal?: string;
  /** Each tax row as computed: a hand-set row whose rate came out null has a zero base. */
  taxes?: { amount_set_by_hand: boolean; rate: string | null; amount: string | null }[];
}): InvoiceWarning[] {
  const warnings: InvoiceWarning[] = [];
  const blank = { service_lines: [], companies: [] };
  if (input.quantities.some((quantity) => quantity.trim() !== "" && Number(quantity) === 0)) {
    warnings.push({ code: "zero_quantity", ...blank });
  }
  if (
    input.taxes?.some(
      (tax) => tax.amount_set_by_hand && tax.amount !== null && tax.rate === null,
    )
  ) {
    warnings.push({ code: "tax_rate_not_derivable", ...blank });
  }
  if (input.subtotal !== undefined && input.subtotal.trim().startsWith("-")) {
    warnings.push({ code: "negative_subtotal", ...blank });
  }
  if (input.payeeCurrency === null) {
    warnings.push({ code: "no_payee_account", ...blank });
  } else if (input.invoiceCurrency && input.payeeCurrency !== input.invoiceCurrency) {
    warnings.push({ code: "payee_currency", ...blank });
  }
  if (!input.paymentTerms && !input.dueDate) {
    warnings.push({ code: "no_due_date", ...blank });
  }
  return warnings;
}

/** The form's live warnings plus those only the server can know (unlocked hours, an
 * inactive company), which come from the last generation or the saved invoice. */
export function combineWarnings(
  live: InvoiceWarning[],
  fromServer: InvoiceWarning[],
): InvoiceWarning[] {
  return [...fromServer.filter((warning) => !FORM_CODES.includes(warning.code)), ...live];
}
