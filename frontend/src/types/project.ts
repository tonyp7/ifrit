export type ProjectType = "time_and_material" | "fixed_price" | "capped_tm";
export type ProjectStatus = "draft" | "active" | "closed";
export type Uom = "hours" | "days" | "ea";

// Single source of truth for value -> display label: raw enum values are never
// shown to the user; every table/select that renders one of these must go
// through this map (then t()).
export const PROJECT_TYPE_LABELS: Record<ProjectType, string> = {
  time_and_material: "Time & Material",
  fixed_price: "Fixed Price",
  capped_tm: "Capped T&M",
};

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "Draft",
  active: "Active",
  closed: "Closed",
};

export const UOM_LABELS: Record<Uom, string> = {
  hours: "Hours",
  days: "Days",
  ea: "Each",
};

// The app's own vocabulary for what a reference is. Raw values are never shown: like the
// maps above, every place that renders one goes through this map (then t()). `custom` is the
// only kind with a label of the user's own.
export type ReferenceKind =
  | "purchase_order"
  | "sales_order"
  | "contract"
  | "buyer_reference"
  | "accounting_reference"
  | "project_reference"
  | "document_reference"
  | "custom";

export const REFERENCE_KIND_LABELS: Record<ReferenceKind, string> = {
  purchase_order: "Purchase order",
  sales_order: "Sales order",
  contract: "Contract",
  buyer_reference: "Buyer reference",
  accounting_reference: "Accounting reference",
  project_reference: "Project reference",
  document_reference: "Document reference",
  custom: "Custom",
};

export interface ProjectReference {
  id: string;
  project_id: string;
  kind: ReferenceKind;
  // Only on a `custom` reference.
  label: string | null;
  value: string;
  position: number;
}

export interface ProjectReferenceInput {
  kind: ReferenceKind;
  label: string | null;
  value: string;
}

export interface ServiceLineConsultant {
  id: string;
  full_name: string;
  // False for a since-deleted user who is still on the line (history): shown in red
  // and removable, but can't be saved back onto a line.
  is_active: boolean;
}

// A conceptually separate assignment from a consultant (project-level authority, not a
// service line's billable-time consultant). No is_active: a deleted user is removed as
// project manager everywhere at deletion time.
export interface ProjectManager {
  id: string;
  full_name: string;
}

export interface ServiceLine {
  id: string;
  project_id: string;
  name: string | null;
  quantity: string;
  uom: Uom;
  unit_price: string;
  value: string;
  is_active: boolean;
  users: ServiceLineConsultant[];
}

export interface ServiceLineInput {
  name: string | null;
  quantity: string;
  uom: Uom;
  unit_price: string;
  user_ids: string[];
}

// An agreed billing installment of a Fixed Price project. Only `value` is stored: the
// percentage shown next to it is always derived from the project's current contract
// value, so it follows service line changes while the value stays put.
export interface BillingMilestone {
  id: string;
  project_id: string;
  description: string;
  // A plain calendar date, `YYYY-MM-DD`: parse it with `parseDayKey`, never `new Date()`.
  due_date: string | null;
  value: string;
  position: number;
}

export interface BillingMilestoneInput {
  description: string;
  due_date: string | null;
  value: string;
}

export interface ProjectListItem {
  id: string;
  name: string;
  status: ProjectStatus;
  project_type: ProjectType;
  // Null only on a duplicate whose source company was soft-deleted.
  client_company_id: string | null;
  client_company_name: string | null;
  vendor_company_id: string | null;
  vendor_company_name: string | null;
  created_at: string;
}

export interface ProjectListResponse {
  items: ProjectListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectDetail {
  id: string;
  name: string;
  // Null only on a duplicate whose source company was soft-deleted. A non-null company
  // with *_is_active === false is still a valid link, but must be replaced on next edit.
  vendor_company_id: string | null;
  vendor_company_name: string | null;
  vendor_company_is_active: boolean | null;
  client_company_id: string | null;
  client_company_name: string | null;
  client_company_is_active: boolean | null;
  invoicing_currency: string;
  project_type: ProjectType;
  status: ProjectStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  service_lines: ServiceLine[];
  project_managers: ProjectManager[];
  // In saved order.
  project_references: ProjectReference[];
  // In saved order. Always empty unless the project is Fixed Price.
  billing_milestones: BillingMilestone[];
  total_value: string;
}

export interface ProjectInput {
  name: string;
  vendor_company_id: string;
  client_company_id: string;
  invoicing_currency: string;
  project_type: ProjectType;
  status: ProjectStatus;
  project_manager_ids: string[];
}
