// Decimal amounts (quantity, unit_price, value, total_value) come from the API as
// strings (see specs/architecture/backend.md — Decimal is JSON-serialized as a string
// to avoid float precision loss). Display them human-readable — see
// specs/requirements/project.md#calculated-values for the two different rules below.

/** `NUMERIC(12, 5)` quantities — decimals shown only when needed, up to 5 places,
 * never padded with trailing zeros (e.g. `1.5`, not `1.50000`; `10`, not `10.00000`). */
export function formatQuantity(value: string): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return value;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 5 }).format(num);
}

/**
 * Monetary amounts: grouped thousands, always showing exactly the currency's own
 * decimal precision (`minor_unit` — e.g. 2 for USD, 0 for JPY), never more or fewer —
 * unlike `formatQuantity`, trailing zeros are kept, not trimmed. Falls back to 2
 * decimals if the currency's minor_unit isn't known yet.
 */
export function formatMoney(value: string, minorUnit: number | null | undefined): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return value;
  const digits = minorUnit ?? 2;
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(num);
}

/**
 * Reverses `formatQuantity`/`formatMoney`'s thousands grouping so an editable field
 * pre-filled with a formatted value (see ServiceLineFormDialog) can be parsed back
 * into a plain decimal string before validation/submission.
 */
export function stripGrouping(value: string): string {
  return value.replace(/,/g, "");
}
