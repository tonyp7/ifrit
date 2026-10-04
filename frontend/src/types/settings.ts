/** The `pdf-export` settings group, exactly as the API returns it. */
export interface PdfExportSettings {
  export_logo: boolean;
  /** Whole millimeters, 1 to 60. */
  logo_height_mm: number;
}

export const LOGO_HEIGHT_MIN_MM = 1;
export const LOGO_HEIGHT_MAX_MM = 60;
