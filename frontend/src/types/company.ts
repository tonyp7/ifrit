export type IdentifierType =
  | "legal_registration"
  | "vat"
  | "peppol_participant"
  | "duns"
  | "gln"
  | "internal";

export type AddressType = "registered" | "bill_to" | "ship_to" | "postal";

export type PaymentMeansCode = "30" | "42" | "58";

export type AccountScheme = "iban" | "other";

// Single source of truth for value -> display label: raw enum values are never
// shown to the user; every table/select that renders one of these must go
// through this map.
export const ID_TYPE_LABELS: Record<IdentifierType, string> = {
  legal_registration: "Legal Registration",
  vat: "VAT",
  peppol_participant: "Peppol Participant",
  duns: "DUNS",
  gln: "GLN",
  internal: "Internal",
};

export const ADDRESS_TYPE_LABELS: Record<AddressType, string> = {
  registered: "Registered",
  bill_to: "Bill To",
  ship_to: "Ship To",
  postal: "Postal",
};

export const PAYMENT_MEANS_LABELS: Record<PaymentMeansCode, string> = {
  "30": "Credit transfer",
  "42": "Payment to bank account",
  "58": "SEPA credit transfer",
};

export const ACCOUNT_SCHEME_LABELS: Record<AccountScheme, string> = {
  iban: "IBAN",
  other: "Other",
};

export interface PartyIdentifier {
  id: string;
  company_id: string;
  id_type: IdentifierType;
  scheme_id: string | null;
  id_value: string;
  is_primary: boolean;
  valid_from: string | null;
  valid_to: string | null;
}

export interface PartyIdentifierInput {
  id_type: IdentifierType;
  scheme_id?: string | null;
  id_value: string;
  is_primary?: boolean;
  valid_from?: string | null;
  valid_to?: string | null;
}

export interface Address {
  id: string;
  company_id: string;
  address_type: AddressType;
  line1: string;
  line2: string | null;
  line3: string | null;
  city: string;
  postal_zone: string | null;
  country_subdivision: string | null;
  country_code: string;
  is_primary: boolean;
  valid_from: string | null;
  valid_to: string | null;
}

export interface AddressInput {
  address_type: AddressType;
  line1: string;
  line2?: string | null;
  line3?: string | null;
  city: string;
  postal_zone?: string | null;
  country_subdivision?: string | null;
  country_code: string;
  is_primary?: boolean;
  valid_from?: string | null;
  valid_to?: string | null;
}

export interface BankAddress {
  line1: string;
  line2: string | null;
  line3: string | null;
  city: string;
  postal_zone: string | null;
  country_subdivision: string | null;
  country_code: string;
}

export interface PayeeAccount {
  id: string;
  company_id: string;
  payment_means_code: PaymentMeansCode;
  account_scheme: AccountScheme;
  account_identifier: string;
  account_name: string | null;
  currency_code: string;
  bic: string | null;
  bank_name: string | null;
  bank_address: BankAddress | null;
  is_primary: boolean;
}

export interface PayeeAccountInput {
  payment_means_code: PaymentMeansCode;
  account_scheme: AccountScheme;
  account_identifier: string;
  account_name?: string | null;
  currency_code: string;
  bic?: string | null;
  bank_name?: string | null;
  bank_address?: BankAddress | null;
  is_primary?: boolean;
}

export interface CompanyListItem {
  id: string;
  legal_name: string;
  trading_name: string | null;
  country_of_registration: string;
}

export interface CompanyListResponse {
  items: CompanyListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CompanyDetail {
  id: string;
  is_vendor: boolean;
  legal_name: string;
  trading_name: string | null;
  legal_form: string | null;
  country_of_registration: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  identifiers: PartyIdentifier[];
  addresses: Address[];
  payee_accounts: PayeeAccount[];
}

export interface CompanyInput {
  is_vendor: boolean;
  legal_name: string;
  trading_name?: string | null;
  legal_form?: string | null;
  country_of_registration: string;
}
