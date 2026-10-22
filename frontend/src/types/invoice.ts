import type {
  AccountScheme,
  AddressType,
  BankAddress,
  IdentifierType,
  PaymentMeansCode,
} from "@/types/company";
import type { ProjectStatus, ProjectType, ReferenceKind, Uom } from "@/types/project";

export type InvoiceStatus = "draft" | "issued" | "void";

export type PaymentTerms =
  | "due_on_receipt"
  | "net_7"
  | "net_15"
  | "net_30"
  | "net_60"
  | "net_90"
  | "eom"
  | "eom_15"
  | "eom_30"
  | "eom_60"
  | "eom_90";

// Single source of truth for value -> display label: raw values are never shown; render
// them through t() with these English source strings.
export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Draft",
  issued: "Issued",
  void: "Void",
};

export const PAYMENT_TERMS_LABELS: Record<PaymentTerms, string> = {
  due_on_receipt: "Due on Receipt",
  net_7: "Net 7",
  net_15: "Net 15",
  net_30: "Net 30",
  net_60: "Net 60",
  net_90: "Net 90",
  eom: "End of Month",
  eom_15: "End of Month + 15",
  eom_30: "End of Month + 30",
  eom_60: "End of Month + 60",
  eom_90: "End of Month + 90",
};

export const PAYMENT_TERMS: PaymentTerms[] = Object.keys(
  PAYMENT_TERMS_LABELS,
) as PaymentTerms[];

export interface Party {
  name: string;
  address: BankAddress | null;
}

/** Payee account details as copied onto an invoice: no id, no primary flag. */
export interface InvoicePayee {
  payment_means_code: PaymentMeansCode;
  account_scheme: AccountScheme;
  account_identifier: string;
  account_name: string | null;
  currency_code: string;
  bic: string | null;
  bank_name: string | null;
  bank_address: BankAddress | null;
}

export interface InvoiceReference {
  kind: ReferenceKind;
  label: string | null;
  value: string;
}

export interface InvoiceLine {
  description: string;
  /** Decimal strings, as the API sends them, so amounts never pass through a float. */
  quantity: string;
  uom: Uom;
  unit_price: string;
  amount: string;
}

export type TaxBaseMode = "subtotal" | "cumulative";

export interface InvoiceTax {
  label: string;
  base_mode: TaxBaseMode;
  /** Null when it cannot be worked back from a hand-set amount (a zero base). */
  rate: string | null;
  amount: string;
  amount_set_by_hand: boolean;
  /** What the row was charged on, as stored by the server. */
  base_amount: string;
}

/** Only the value typed counts: `rate` for a rate-driven row, `amount` for a hand-set one. */
export interface InvoiceTaxInput {
  label: string;
  base_mode: TaxBaseMode;
  rate: string | null;
  amount: string | null;
  amount_set_by_hand: boolean;
}

export type InvoiceWarningCode =
  | "unlocked_hours"
  | "zero_quantity"
  | "no_payee_account"
  | "payee_currency"
  | "inactive_company"
  | "due_before_invoice_date"
  | "no_due_date"
  | "tax_rate_not_derivable"
  | "negative_subtotal";

export interface UnlockedServiceLine {
  name: string | null;
  uom: Uom;
  unit_price: string;
  days: number;
}

export interface InvoiceWarning {
  code: InvoiceWarningCode;
  service_lines: UnlockedServiceLine[];
  companies: ("vendor" | "client")[];
}

export interface InvoiceDetail {
  id: string;
  status: InvoiceStatus;
  project_id: string;
  project_name: string;
  currency_code: string;
  currency_minor_unit: number | null;
  bill_from: Party;
  bill_to: Party;
  period_start: string | null;
  period_end: string | null;
  payment_terms: PaymentTerms | null;
  due_date: string | null;
  payee: InvoicePayee | null;
  references: InvoiceReference[];
  lines: InvoiceLine[];
  subtotal: string;
  taxes: InvoiceTax[];
  total: string;
  created_at: string;
  updated_at: string;
  warnings: InvoiceWarning[];
  /** Set once issued; null on a draft. */
  number: string | null;
  invoice_date: string | null;
  document_name: string | null;
  vendor_identifiers: SnapshotIdentifier[];
  client_identifiers: SnapshotIdentifier[];
  issued_at: string | null;
  issued_by_name: string | null;
  voided_at: string | null;
  voided_by_name: string | null;
  void_reason: string | null;
  /** The PDF kept when the invoice was issued; false on a draft and on an invoice issued
   * before PDFs were kept. */
  has_pdf: boolean;
}

/** A company identifier as it stood when the invoice was issued. */
export interface SnapshotIdentifier {
  id_type: IdentifierType;
  scheme_id: string | null;
  id_value: string;
  is_primary: boolean;
}

export interface InvoiceLineInput {
  description: string;
  quantity: string;
  uom: Uom;
  unit_price: string;
}

export interface InvoiceInput {
  project_id: string;
  bill_from: Party;
  bill_to: Party;
  period_start: string | null;
  period_end: string | null;
  payment_terms: PaymentTerms | null;
  due_date: string | null;
  payee: InvoicePayee | null;
  references: InvoiceReference[];
  lines: InvoiceLineInput[];
  taxes: InvoiceTaxInput[];
}

export interface InvoiceListItem {
  id: string;
  status: InvoiceStatus;
  project_id: string;
  project_name: string;
  client_name: string;
  period_start: string | null;
  period_end: string | null;
  currency_code: string;
  currency_minor_unit: number | null;
  total: string;
  payment_terms: PaymentTerms | null;
  due_date: string | null;
  created_at: string;
  number: string | null;
  invoice_date: string | null;
  issued_at: string | null;
  /** What Billed for shows when there is no period (a Fixed Price invoice): every line's
   * description in order, joined with ", ". Null when the invoice has no line. */
  lines_summary: string | null;
  has_pdf: boolean;
}

export interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface InvoiceableProject {
  id: string;
  name: string;
  project_type: ProjectType;
  status: ProjectStatus;
  client_name: string | null;
  currency_code: string;
}

export interface ContextAddress extends BankAddress {
  id: string;
  address_type: AddressType;
  is_primary: boolean;
}

export interface ContextCompany {
  id: string;
  display_name: string;
  is_active: boolean;
  addresses: ContextAddress[];
}

export interface ContextPayeeAccount extends InvoicePayee {
  id: string;
  is_primary: boolean;
}

export interface ContextServiceLine {
  id: string;
  name: string | null;
  uom: Uom;
  unit_price: string;
}

export interface ContextMilestone {
  id: string;
  description: string;
  due_date: string | null;
  value: string;
}

/** What the invoice form knows about a project, read through the invoice API. */
export interface BillingContext {
  id: string;
  name: string;
  project_type: ProjectType;
  status: ProjectStatus;
  is_active: boolean;
  currency_code: string;
  currency_minor_unit: number | null;
  vendor: ContextCompany | null;
  client: ContextCompany | null;
  payee_accounts: ContextPayeeAccount[];
  service_lines: ContextServiceLine[];
  /** In their order; empty unless the project is Fixed Price. */
  milestones: ContextMilestone[];
  references: InvoiceReference[];
}

/** Lines from the hours logged on service lines (T&M and Capped T&M) or one per milestone
 * (Fixed Price). */
export type GenerateInput =
  | {
      kind: "time";
      project_id: string;
      service_line_ids: string[];
      period_start: string;
      period_end: string;
    }
  | { kind: "milestone"; project_id: string; milestone_ids: string[] };

export interface GeneratedLine {
  name: string | null;
  quantity: string;
  uom: Uom;
  unit_price: string;
}

export interface OmittedServiceLine {
  service_line_id: string;
  name: string | null;
  uom: Uom;
  unit_price: string;
}

export interface GenerateResult {
  lines: GeneratedLine[];
  omitted: OmittedServiceLine[];
  warnings: InvoiceWarning[];
}

export type BlockingReason = "project_not_active" | "no_lines";

/** What issuing a draft today would give; the number is the likely one, not reserved. */
export interface IssuePreview {
  invoice_date: string;
  due_date: string | null;
  payment_terms: PaymentTerms | null;
  number: string;
  warnings: InvoiceWarning[];
  blocking: BlockingReason[];
}

export const INVOICE_STATUSES: InvoiceStatus[] = ["draft", "issued", "void"];
/** What the list shows when no status is picked: void invoices are hidden unless asked for. */
export const DEFAULT_STATUS_FILTER: InvoiceStatus[] = ["draft", "issued"];
