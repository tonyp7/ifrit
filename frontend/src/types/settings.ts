/** The `pdf-export` settings group, exactly as the API returns it. */
export interface PdfExportSettings {
  export_logo: boolean;
  /** Whole millimeters, 1 to 60. */
  logo_height_mm: number;
}

export const LOGO_HEIGHT_MIN_MM = 1;
export const LOGO_HEIGHT_MAX_MM = 60;

/** The `general` settings group, exactly as the API returns it. */
export interface GeneralSettings {
  /** Whole seconds, 1800 (00:30:00) to 86400 (24:00:00). */
  standard_workday_seconds: number;
}

export const WORKDAY_MIN_SECONDS = 1800;
export const WORKDAY_MAX_SECONDS = 86400;

/** The `invoicing` settings group, exactly as the API returns it. */
export interface InvoicingSettings {
  /** 1 to 60 characters, stored trimmed. */
  document_name: string;
}

export const DOCUMENT_NAME_MAX_LENGTH = 60;
