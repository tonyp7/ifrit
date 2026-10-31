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

export type BannerIcon = "none" | "info" | "warning";
export type BannerColor = "neutral" | "blue" | "yellow" | "red";

/** The `information-banner` settings group, exactly as the API returns it. */
export interface InformationBannerSettings {
  show_on_login: boolean;
  show_site_wide: boolean;
  /** Plain text, stored trimmed, 0 to 200 characters, line breaks allowed. */
  message: string;
  icon: BannerIcon;
  color: BannerColor;
}

export const BANNER_MESSAGE_MAX_LENGTH = 200;

/** One place a banner is shown, as the public read returns it. */
export interface BannerPlacement {
  message: string;
  icon: BannerIcon;
  color: BannerColor;
}

/** What `GET /api/information-banner` returns: null means show nothing there. */
export interface PublicBanner {
  login: BannerPlacement | null;
  site_wide: BannerPlacement | null;
}
