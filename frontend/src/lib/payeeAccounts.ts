import type {
  AccountScheme,
  BankAddress,
  PayeeAccount,
  PayeeAccountInput,
  PaymentMeansCode,
} from "@/types/company";

export type AddressFieldName =
  | "line1"
  | "line2"
  | "line3"
  | "city"
  | "postal_zone"
  | "country_subdivision"
  | "country_code";

export type AddressFieldValues = Record<AddressFieldName, string>;

export interface PayeeAccountFormValues {
  payment_means_code: PaymentMeansCode;
  account_scheme: AccountScheme;
  account_identifier: string;
  account_name: string;
  currency_code: string;
  bic: string;
  bank_name: string;
  bank_address: AddressFieldValues;
  is_primary: boolean;
}

export const BLANK_ADDRESS_FIELDS: AddressFieldValues = {
  line1: "",
  line2: "",
  line3: "",
  city: "",
  postal_zone: "",
  country_subdivision: "",
  country_code: "",
};

// SEPA credit transfer first: it is what most accounts in the enabled currencies are.
export const BLANK_PAYEE_ACCOUNT_VALUES: PayeeAccountFormValues = {
  payment_means_code: "58",
  account_scheme: "iban",
  account_identifier: "",
  account_name: "",
  currency_code: "",
  bic: "",
  bank_name: "",
  bank_address: BLANK_ADDRESS_FIELDS,
  is_primary: false,
};

/** The scheme to keep once the payment means changes: a SEPA credit transfer is addressed
 * by IBAN by definition, so picking it switches the scheme; any other code leaves it be. */
export function schemeForPaymentMeans(
  code: PaymentMeansCode,
  current: AccountScheme,
): AccountScheme {
  return code === "58" ? "iban" : current;
}

/** An IBAN as one value: no spaces, upper case. That is how it is stored and compared. */
export function compactIban(value: string): string {
  return value.replace(/\s+/g, "").toUpperCase();
}

/**
 * ISO 13616 check on a compact IBAN: move the first four characters to the end, read every
 * letter as a number (A=10 .. Z=35), and the whole must leave 1 modulo 97. Reduced one
 * digit at a time, since the number is far beyond what a JS number holds exactly.
 */
export function isValidIban(compact: string): boolean {
  if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$/.test(compact)) return false;
  const digits = [...(compact.slice(4) + compact.slice(0, 4))]
    .map((char) => parseInt(char, 36).toString())
    .join("");
  let remainder = 0;
  for (const digit of digits) remainder = (remainder * 10 + Number(digit)) % 97;
  return remainder === 1;
}

/** Loose on purpose: since 2022 a BIC's first four characters may hold digits too. */
export function isValidBic(value: string): boolean {
  return /^[A-Z0-9]{8}([A-Z0-9]{3})?$/.test(value.trim().toUpperCase());
}

/** For display only: an IBAN in groups of four, the way it is printed; anything else as is. */
export function formatAccountIdentifier(scheme: AccountScheme, value: string): string {
  if (scheme !== "iban") return value;
  return compactIban(value).replace(/(.{4})(?=.)/g, "$1 ");
}

export function isAddressEmpty(address: AddressFieldValues): boolean {
  return Object.values(address).every((value) => !value.trim());
}

/**
 * Which required fields a started bank address still lacks: none when the address is
 * empty altogether, since having no bank address is fine, but a city with no street or
 * country is not an address anyone can use.
 */
export function missingBankAddressFields(
  address: AddressFieldValues,
): ("line1" | "city" | "country_code")[] {
  if (isAddressEmpty(address)) return [];
  const missing: ("line1" | "city" | "country_code")[] = [];
  if (!address.line1.trim()) missing.push("line1");
  if (!address.city.trim()) missing.push("city");
  if (address.country_code.trim().length !== 2) missing.push("country_code");
  return missing;
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function toBankAddress(address: AddressFieldValues): BankAddress | null {
  if (isAddressEmpty(address)) return null;
  return {
    line1: address.line1.trim(),
    line2: blankToNull(address.line2),
    line3: blankToNull(address.line3),
    city: address.city.trim(),
    postal_zone: blankToNull(address.postal_zone),
    country_subdivision: blankToNull(address.country_subdivision),
    country_code: address.country_code.trim().toUpperCase(),
  };
}

export function toPayeeAccountInput(values: PayeeAccountFormValues): PayeeAccountInput {
  const bic = blankToNull(values.bic);
  return {
    payment_means_code: values.payment_means_code,
    account_scheme: values.account_scheme,
    account_identifier:
      values.account_scheme === "iban"
        ? compactIban(values.account_identifier)
        : values.account_identifier.trim(),
    account_name: blankToNull(values.account_name),
    currency_code: values.currency_code,
    bic: bic && bic.toUpperCase(),
    bank_name: blankToNull(values.bank_name),
    bank_address: toBankAddress(values.bank_address),
    is_primary: values.is_primary,
  };
}

// A PayeeAccount's nullable fields don't line up with the form's plain strings: map
// explicitly rather than spreading the entity.
export function toPayeeAccountFormValues(account: PayeeAccount): PayeeAccountFormValues {
  const address = account.bank_address;
  return {
    payment_means_code: account.payment_means_code,
    account_scheme: account.account_scheme,
    account_identifier: formatAccountIdentifier(
      account.account_scheme,
      account.account_identifier,
    ),
    account_name: account.account_name ?? "",
    currency_code: account.currency_code,
    bic: account.bic ?? "",
    bank_name: account.bank_name ?? "",
    bank_address: address
      ? {
          line1: address.line1,
          line2: address.line2 ?? "",
          line3: address.line3 ?? "",
          city: address.city,
          postal_zone: address.postal_zone ?? "",
          country_subdivision: address.country_subdivision ?? "",
          country_code: address.country_code,
        }
      : BLANK_ADDRESS_FIELDS,
    is_primary: account.is_primary,
  };
}
