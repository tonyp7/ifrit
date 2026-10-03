// Decimal amounts (quantity, unit_price, value, total_value) come from the API as
// strings: the backend serializes Decimal fields as strings specifically to avoid
// float precision loss over JSON. Display them human-readable via the two different
// rules below.

/** `NUMERIC(12, 5)` quantities: decimals shown only when needed, up to 5 places,
 * never padded with trailing zeros (e.g. `1.5`, not `1.50000`; `10`, not `10.00000`). */
export function formatQuantity(value: string): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return value;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 5 }).format(num);
}

/**
 * Monetary amounts: grouped thousands, always showing exactly the currency's own
 * decimal precision (`minor_unit`: e.g. 2 for USD, 0 for JPY), never more or fewer:
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

/** A file size as people read it: `512 B`, `1.4 KB`, `2.1 MB`. Decimal units, one decimal
 * at most, like the file managers users compare it against. */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < units.length - 1) {
    value /= 1000;
    unit += 1;
  }
  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: unit === 0 ? 0 : 1,
  }).format(value);
  return `${formatted} ${units[unit]}`;
}
