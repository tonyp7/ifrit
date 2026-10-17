import type { InvoiceWarning, InvoiceWarningCode } from "@/types/invoice";

// Warnings that depend only on what the form holds, worked out live as it changes, by the
// same rules the server uses on a saved invoice.
const FORM_CODES: InvoiceWarningCode[] = [
  "zero_quantity",
  "no_payee_account",
  "payee_currency",
];

export function formWarnings(input: {
  quantities: string[];
  payeeCurrency: string | null;
  invoiceCurrency: string | null;
}): InvoiceWarning[] {
  const warnings: InvoiceWarning[] = [];
  const blank = { service_lines: [], companies: [] };
  if (input.quantities.some((quantity) => quantity.trim() !== "" && Number(quantity) === 0)) {
    warnings.push({ code: "zero_quantity", ...blank });
  }
  if (input.payeeCurrency === null) {
    warnings.push({ code: "no_payee_account", ...blank });
  } else if (input.invoiceCurrency && input.payeeCurrency !== input.invoiceCurrency) {
    warnings.push({ code: "payee_currency", ...blank });
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
