/** The template invoice PDFs are made from. */
export interface InvoiceTemplateInfo {
  source: "default" | "custom";
  filename: string;
  size_bytes: number;
  uploaded_by_name: string | null;
  uploaded_at: string | null;
  placeholders: string[];
}

/** One problem or warning about a template file: where it is and what is wrong. */
export interface TemplateFinding {
  part: string;
  message: string;
  snippet: string | null;
}

export interface InvoiceTemplateSaved extends InvoiceTemplateInfo {
  warnings: TemplateFinding[];
}

/** What a rejected template comes back with. */
export interface TemplateRejection {
  problems: TemplateFinding[];
  warnings: TemplateFinding[];
}
