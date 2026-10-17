// Billing milestone arithmetic on the API's decimal strings. Amounts arrive as strings so
// they never pass through a float (see lib/format.ts); multiplying them as `Number`s would
// bring the drift back (33.33% of 10,000 coming out as 3332.9999...), so these helpers
// scale every operand to a `BigInt` and round only once, at the end.

interface Scaled {
  digits: bigint;
  scale: number;
}

const DECIMAL = /^(-)?(\d+)(?:\.(\d*))?$/;

function parse(value: string): Scaled | null {
  const match = DECIMAL.exec(value.trim());
  if (!match) return null;
  const [, sign, whole, fraction = ""] = match;
  const digits = BigInt(whole + fraction);
  return { digits: sign ? -digits : digits, scale: fraction.length };
}

function pow10(exponent: number): bigint {
  return 10n ** BigInt(exponent);
}

/** `numerator / denominator` rounded half away from zero (the usual commercial rounding);
 * `denominator` must be positive. */
function divideRounded(numerator: bigint, denominator: bigint): bigint {
  const quotient = numerator / denominator;
  const remainder = numerator % denominator;
  const negative = numerator < 0n;
  const absRemainder = negative ? -remainder : remainder;
  if (absRemainder * 2n >= denominator) return negative ? quotient - 1n : quotient + 1n;
  return quotient;
}

function format(digits: bigint, scale: number): string {
  const negative = digits < 0n;
  const text = (negative ? -digits : digits).toString().padStart(scale + 1, "0");
  const whole = scale > 0 ? text.slice(0, -scale) : text;
  const fraction = scale > 0 ? `.${text.slice(-scale)}` : "";
  return `${negative ? "-" : ""}${whole}${fraction}`;
}

/** A currency's decimal places for milestone values: a currency with no minor unit (e.g.
 * gold) is entered and shown with 2, the same fallback as `formatMoney`. */
export function milestoneDecimals(minorUnit: number | null | undefined): number {
  return minorUnit ?? 2;
}

/** `value` rounded half away from zero to `decimals` places, e.g. `100.5` → `"101"` at 0. */
export function roundDecimal(value: string, decimals: number): string | null {
  const parsed = parse(value);
  if (!parsed) return null;
  const shift = decimals - parsed.scale;
  const digits =
    shift >= 0 ? parsed.digits * pow10(shift) : divideRounded(parsed.digits, pow10(-shift));
  return format(digits, decimals);
}

/** The value of `percent`% of `contract`, rounded to the currency's decimals. */
export function percentToValue(
  contract: string,
  percent: string,
  minorUnit: number | null | undefined,
): string | null {
  const c = parse(contract);
  const p = parse(percent);
  if (!c || !p) return null;
  const decimals = milestoneDecimals(minorUnit);
  // contract × percent / 100, expressed in units of 10^-decimals.
  const numerator = c.digits * p.digits * pow10(decimals);
  const denominator = 100n * pow10(c.scale + p.scale);
  return format(divideRounded(numerator, denominator), decimals);
}

/** `value`'s share of `contract` in percent, rounded to 2 decimals; `null` when the
 * contract value is zero (no share to compute). */
export function valueToPercent(value: string, contract: string): string | null {
  const v = parse(value);
  const c = parse(contract);
  if (!v || !c || c.digits === 0n) return null;
  // value / contract × 100, expressed in hundredths of a percent.
  let numerator = v.digits * pow10(c.scale) * 10000n;
  let denominator = c.digits * pow10(v.scale);
  if (denominator < 0n) {
    numerator = -numerator;
    denominator = -denominator;
  }
  return format(divideRounded(numerator, denominator), 2);
}

/** The exact product of two decimal strings, unrounded; `null` when either is not a number. */
export function multiplyDecimal(a: string, b: string): string | null {
  const x = parse(a);
  const y = parse(b);
  if (!x || !y) return null;
  return format(x.digits * y.digits, x.scale + y.scale);
}

/** The exact sum of `values`, at the largest scale among them. */
export function sumValues(values: string[]): string {
  const parsed = values.map(parse).filter((v): v is Scaled => v !== null);
  const scale = Math.max(0, ...parsed.map((v) => v.scale));
  const total = parsed.reduce((sum, v) => sum + v.digits * pow10(scale - v.scale), 0n);
  return format(total, scale);
}

/** Whether the milestone total and the contract value differ once both are rounded to the
 * currency's decimals, so leftovers below the currency's precision never count. */
export function differsFromContract(
  sum: string,
  contract: string,
  minorUnit: number | null | undefined,
): boolean {
  const decimals = milestoneDecimals(minorUnit);
  return roundDecimal(sum, decimals) !== roundDecimal(contract, decimals);
}
