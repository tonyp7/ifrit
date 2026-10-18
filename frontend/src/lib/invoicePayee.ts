import {
  BLANK_PAYEE_ACCOUNT_VALUES,
  type PayeeAccountFormValues,
  toPayeeAccountFormValues,
  toPayeeAccountInput,
} from "@/lib/payeeAccounts";
import type { ContextPayeeAccount, InvoicePayee } from "@/types/invoice";

/** The vendor account to copy onto a new draft: the primary one in the invoice currency,
 * else the only one in that currency, else none (several and no primary is the user's
 * call). */
export function preselectPayee(
  accounts: ContextPayeeAccount[],
  currency: string,
): ContextPayeeAccount | null {
  const inCurrency = accounts.filter((account) => account.currency_code === currency);
  return (
    inCurrency.find((account) => account.is_primary) ??
    (inCurrency.length === 1 ? inCurrency[0] : null)
  );
}

/** The dropdown's order: accounts in the invoice currency first, otherwise as received. */
export function orderPayeeAccounts(
  accounts: ContextPayeeAccount[],
  currency: string,
): ContextPayeeAccount[] {
  return [
    ...accounts.filter((account) => account.currency_code === currency),
    ...accounts.filter((account) => account.currency_code !== currency),
  ];
}

/** The payee fields of the form, filled from one of the vendor's accounts. A copy: nothing
 * keeps a link to the account it came from. */
export function payeeFormFromAccount(account: ContextPayeeAccount): PayeeAccountFormValues {
  return toPayeeAccountFormValues({ ...account, company_id: "" });
}

export function payeeFormFromInvoice(
  payee: InvoicePayee | null,
): PayeeAccountFormValues | null {
  return payee
    ? toPayeeAccountFormValues({ ...payee, id: "", company_id: "", is_primary: false })
    : null;
}

/** The payee fields as the API's payee body, without the company-only primary flag. */
export function toInvoicePayee(values: PayeeAccountFormValues): InvoicePayee {
  const { is_primary: _primary, ...payee } = toPayeeAccountInput(values);
  return {
    ...payee,
    account_name: payee.account_name ?? null,
    bic: payee.bic ?? null,
    bank_name: payee.bank_name ?? null,
    bank_address: payee.bank_address ?? null,
  };
}

export const BLANK_INVOICE_PAYEE = BLANK_PAYEE_ACCOUNT_VALUES;
