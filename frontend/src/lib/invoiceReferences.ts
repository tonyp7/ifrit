import type { InvoiceReference } from "@/types/invoice";
import type { ReferenceKind } from "@/types/project";

/** A reference row on the draft. `options` holds the project's values for a kind that has
 * several, for the user to pick the one this invoice is for. */
export interface InvoiceReferenceRow {
  kind: ReferenceKind;
  label: string;
  value: string;
  options: string[];
}

// Most e-invoicing targets take one value of these per invoice, so several on the project
// means a choice; document and custom references are not limited and all carry over.
const CARRIED_IN_FULL: ReferenceKind[] = ["document_reference", "custom"];

/** The rows a new draft starts with, from the project's references in their order. */
export function prefillReferences(
  projectReferences: InvoiceReference[],
): InvoiceReferenceRow[] {
  const rows: InvoiceReferenceRow[] = [];
  const valuesByKind = new Map<ReferenceKind, string[]>();
  for (const reference of projectReferences) {
    if (CARRIED_IN_FULL.includes(reference.kind)) {
      rows.push({
        kind: reference.kind,
        label: reference.label ?? "",
        value: reference.value,
        options: [],
      });
      continue;
    }
    const values = valuesByKind.get(reference.kind);
    if (values) {
      values.push(reference.value);
      continue;
    }
    const fresh = [reference.value];
    valuesByKind.set(reference.kind, fresh);
    // Placeholder at the kind's first position, settled once every value is known.
    rows.push({ kind: reference.kind, label: "", value: "", options: fresh });
  }
  return rows.map((row) =>
    row.options.length === 1 ? { ...row, value: row.options[0], options: [] } : row,
  );
}

export function rowsFromInvoice(references: InvoiceReference[]): InvoiceReferenceRow[] {
  return references.map((r) => ({
    kind: r.kind,
    label: r.label ?? "",
    value: r.value,
    options: [],
  }));
}

/** The rows as the API's references. Empty rows must be fixed first (see `emptyRows`). */
export function toInvoiceReferences(rows: InvoiceReferenceRow[]): InvoiceReference[] {
  return rows.map((row) => ({
    kind: row.kind,
    label: row.kind === "custom" ? row.label.trim() : null,
    value: row.value.trim(),
  }));
}

/** Indexes of rows that would block saving: no value, or a custom row with no label. */
export function emptyRows(rows: InvoiceReferenceRow[]): number[] {
  return rows.flatMap((row, index) =>
    !row.value.trim() || (row.kind === "custom" && !row.label.trim()) ? [index] : [],
  );
}
