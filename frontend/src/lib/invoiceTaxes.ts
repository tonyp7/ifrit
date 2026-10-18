import {
  milestoneDecimals,
  percentToValue,
  roundDecimal,
  sumValues,
  valueToPercent,
} from "@/lib/milestoneMath";

// Invoice taxes on decimal strings, never through a float, by the same rules the server
// stores them with: what the form shows is what gets saved.

import type { TaxBaseMode } from "@/types/invoice";

export type { TaxBaseMode };

// Tax names are kept as typed: they differ by country, so these only save typing. Only the
// zero-rate ones come with a rate, because any other default rate would be wrong somewhere.
export const TAX_PRESETS = [
  "GST",
  "VAT",
  "Sales Tax",
  "Standard-Rate",
  "Zero-Rate",
  "Tax-Exempt",
] as const;
export const ZERO_RATE_PRESETS: readonly string[] = ["Zero-Rate", "Tax-Exempt"];

/** What choosing a label changes on its row: a zero-rate preset also sets a 0 % rate and
 * makes the row rate-driven; anything else, picked or typed, sets only the label. */
export function labelChange(
  label: string,
  preset: boolean,
): { label: string; rate?: string; amount_set_by_hand?: boolean } {
  return preset && ZERO_RATE_PRESETS.includes(label)
    ? { label, rate: "0", amount_set_by_hand: false }
    : { label };
}

/** Translation keys for the Applies to choices. */
export const TAX_BASE_MODE_LABELS: Record<TaxBaseMode, string> = {
  subtotal: "Subtotal",
  cumulative: "Subtotal + taxes above",
};

/** Whether a dropdown's value is one of the Applies to choices. A Radix `Select` that mounts
 * inside a form can report an empty value, which must not overwrite the row's choice. */
export function isTaxBaseMode(value: string): value is TaxBaseMode {
  return Object.hasOwn(TAX_BASE_MODE_LABELS, value);
}

export interface TaxRowInput {
  base_mode: TaxBaseMode;
  /** The typed rate; what counts for a rate-driven row. */
  rate: string;
  /** The typed amount; what counts for a row whose amount is set by hand. */
  amount: string;
  amount_set_by_hand: boolean;
}

export interface ComputedTaxRow {
  /** "subtotal" on the first row whatever was chosen: both give the same base there. */
  baseMode: TaxBaseMode;
  /** What the row is charged on: the subtotal, plus the rows above when compounding. */
  base: string;
  /** The typed rate, or the one worked back from a hand-set amount; `null` when it cannot
   * be worked out (a zero base) or the typed value is not a number. */
  rate: string | null;
  /** `null` while the typed value is not a number. */
  amount: string | null;
}

const RATE_DECIMALS = 3;
// A rate worked back on a tiny base can be too large for the database's NUMERIC(12, 3); the
// server stores it as unknown, so the form shows it that way too.
const RATE_LIMIT_DIGITS = 9;

function fitsRate(rate: string): boolean {
  return rate.replace("-", "").split(".")[0].length <= RATE_LIMIT_DIGITS;
}

/** Each row in order, as the server computes it on save. */
export function computeTaxes(
  subtotal: string,
  rows: TaxRowInput[],
  minorUnit: number | null | undefined,
): ComputedTaxRow[] {
  const decimals = milestoneDecimals(minorUnit);
  const above: string[] = [];
  return rows.map((row, index) => {
    const baseMode: TaxBaseMode = index === 0 ? "subtotal" : row.base_mode;
    const base =
      roundDecimal(
        baseMode === "cumulative" ? sumValues([subtotal, ...above]) : subtotal,
        decimals,
      ) ?? subtotal;
    let rate: string | null;
    let amount: string | null;
    if (row.amount_set_by_hand) {
      amount = roundDecimal(row.amount.trim(), decimals);
      rate = amount === null ? null : valueToPercent(amount, base, RATE_DECIMALS);
      if (rate !== null && !fitsRate(rate)) rate = null;
    } else {
      rate = roundDecimal(row.rate.trim(), RATE_DECIMALS) === null ? null : row.rate.trim();
      amount = rate === null ? null : percentToValue(base, rate, minorUnit);
    }
    if (amount !== null) above.push(amount);
    return { baseMode, base, rate, amount };
  });
}

/** Subtotal plus every tax amount that can be computed, at the currency's decimals. */
export function totalWithTaxes(
  subtotal: string,
  taxes: ComputedTaxRow[],
  minorUnit: number | null | undefined,
): string {
  const amounts = taxes.map((tax) => tax.amount).filter((a): a is string => a !== null);
  return (
    roundDecimal(sumValues([subtotal, ...amounts]), milestoneDecimals(minorUnit)) ?? subtotal
  );
}

/** A rate as shown: up to 3 decimals, trailing zeros dropped ("5", "9.975", "0.525"). */
export function displayRate(rate: string): string {
  return rate.includes(".") ? rate.replace(/\.?0+$/, "") : rate;
}
