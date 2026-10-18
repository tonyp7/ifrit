import { describe, expect, it } from "vitest";

import { emptyRows, prefillReferences, toInvoiceReferences } from "@/lib/invoiceReferences";
import type { InvoiceReference } from "@/types/invoice";

const ref = (kind: InvoiceReference["kind"], value: string, label: string | null = null) => ({
  kind,
  value,
  label,
});

describe("prefillReferences", () => {
  it("pre-fills a kind with exactly one value", () => {
    expect(prefillReferences([ref("purchase_order", "PO-2026-014")])).toEqual([
      { kind: "purchase_order", label: "", value: "PO-2026-014", options: [] },
    ]);
  });

  it("asks which value for a kind with several", () => {
    expect(
      prefillReferences([
        ref("purchase_order", "PO-1"),
        ref("contract", "CT-1"),
        ref("purchase_order", "PO-2"),
      ]),
    ).toEqual([
      { kind: "purchase_order", label: "", value: "", options: ["PO-1", "PO-2"] },
      { kind: "contract", label: "", value: "CT-1", options: [] },
    ]);
  });

  it("leaves out kinds the project has none of", () => {
    expect(prefillReferences([])).toEqual([]);
  });

  it("carries every document and custom reference", () => {
    const rows = prefillReferences([
      ref("document_reference", "D-1"),
      ref("document_reference", "D-2"),
      ref("custom", "FW-1", "Framework"),
    ]);
    expect(rows.map((row) => [row.kind, row.value, row.label])).toEqual([
      ["document_reference", "D-1", ""],
      ["document_reference", "D-2", ""],
      ["custom", "FW-1", "Framework"],
    ]);
  });
});

describe("saving references", () => {
  it("flags rows with no value or a custom row with no label", () => {
    const rows = [
      { kind: "purchase_order" as const, label: "", value: "", options: ["PO-1", "PO-2"] },
      { kind: "contract" as const, label: "", value: "CT-1", options: [] },
      { kind: "custom" as const, label: " ", value: "X", options: [] },
    ];
    expect(emptyRows(rows)).toEqual([0, 2]);
  });

  it("drops labels on typed kinds and trims", () => {
    expect(
      toInvoiceReferences([
        { kind: "contract", label: "ignored", value: " CT-1 ", options: [] },
      ]),
    ).toEqual([{ kind: "contract", label: null, value: "CT-1" }]);
  });
});
