export type ProjectType = "time_and_material" | "fixed_price" | "capped_tm";
export type ProjectStatus = "draft" | "active" | "closed";
export type Uom = "hours" | "days" | "ea";

// Single source of truth for value -> display label — raw enum values are never
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

export interface ServiceLineConsultant {
  id: string;
  full_name: string;
}

// Same shape as ServiceLineConsultant — kept as a distinct name since it's a
// conceptually separate assignment (project-level authority, not a service line's
// billable-time consultant).
export type ProjectManager = ServiceLineConsultant;

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

export interface ProjectListItem {
  id: string;
  name: string;
  status: ProjectStatus;
  project_type: ProjectType;
  client_company_id: string;
  client_company_name: string;
  vendor_company_id: string;
  vendor_company_name: string;
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
  vendor_company_id: string;
  client_company_id: string;
  invoicing_currency: string;
  project_type: ProjectType;
  status: ProjectStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  service_lines: ServiceLine[];
  project_managers: ProjectManager[];
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
