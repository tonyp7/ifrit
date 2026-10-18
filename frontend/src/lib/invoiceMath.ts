import {
  milestoneDecimals,
  multiplyDecimal,
  roundDecimal,
  sumValues,
} from "@/lib/milestoneMath";

// Invoice amounts on the API's decimal strings, never through a float, rounded half away
// from zero to the currency's decimals: the same rule the server applies when it stores
// them, so what the form shows is what gets saved.

/** quantity × unit price, rounded to the currency's decimals; `null` while either field
 * holds something that is not a number. */
export function lineAmount(
  quantity: string,
  unitPrice: string,
  minorUnit: number | null | undefined,
): string | null {
  const product = multiplyDecimal(quantity.trim(), unitPrice.trim());
  return product === null ? null : roundDecimal(product, milestoneDecimals(minorUnit));
}

/** The sum of the line amounts that can be computed, at the currency's decimals. */
export function subtotal(
  lines: { quantity: string; unit_price: string }[],
  minorUnit: number | null | undefined,
): string {
  const amounts = lines
    .map((line) => lineAmount(line.quantity, line.unit_price, minorUnit))
    .filter((amount): amount is string => amount !== null);
  return roundDecimal(sumValues(amounts), milestoneDecimals(minorUnit)) ?? "0";
}
