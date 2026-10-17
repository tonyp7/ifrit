import { apiClient } from "@/api/client";
import type { NumberingState, NumberingToken } from "@/types/invoiceNumbering";

const PATH = "/invoice-numbering";

export function getNumbering() {
  return apiClient.get<NumberingState>(PATH);
}

/** `confirm` is required once invoices have been issued; the server answers 409 without it. */
export function saveNumberingFormat(tokens: NumberingToken[], confirm: boolean) {
  return apiClient.put<NumberingState>(PATH, { tokens, confirm });
}

export function setNextNumber(nextValue: number) {
  return apiClient.put<NumberingState>(`${PATH}/next`, { next_value: nextValue });
}
