import {
  BLANK_PAYEE_ACCOUNT_VALUES,
  type PayeeAccountFormValues,
  toPayeeAccountFormValues,
  toPayeeAccountInput,
} from "@/lib/payeeAccounts";
import type { ContextPayeeAccount, InvoicePayee } from "@/types/invoice";

/** How well an account suits the invoice: 1 the primary one in the invoice currency, 2 any
 * in that currency, 3 a primary one in another currency, 4 anything else. */
function payeeRank(account: ContextPayeeAccount, currency: string): number {
  if (account.currency_code === currency) return account.is_primary ? 1 : 2;
  return account.is_primary ? 3 : 4;
}

/** The vendor account to copy onto a new draft: the best-ranked one (see `payeeRank`), the
 * lowest id deciding between equals, so the pick does not depend on the order received. The
 * ids are compared as plain strings, as the server orders them. A vendor with an account in
 * another currency only still gets it: the payee currency warning flags the difference. Null
 * only when the vendor has no account. */
export function preselectPayee(
  accounts: ContextPayeeAccount[],
  currency: string,
): ContextPayeeAccount | null {
  let best: ContextPayeeAccount | null = null;
  for (const account of accounts) {
    if (best === null) {
      best = account;
      continue;
    }
    const rank = payeeRank(account, currency);
    const bestRank = payeeRank(best, currency);
    if (rank < bestRank || (rank === bestRank && account.id < best.id)) best = account;
  }
  return best;
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
