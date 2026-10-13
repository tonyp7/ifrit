import { describe, expect, it } from "vitest";

import {
  BLANK_REFERENCE_FORM,
  MAX_PROJECT_REFERENCES,
  REFERENCE_KINDS,
  referenceName,
  referenceToFormValues,
  toReferenceInput,
  withKind,
} from "@/lib/projectReferences";
import type { ProjectReference } from "@/types/project";

const reference = (
  kind: ProjectReference["kind"],
  value: string,
  label: string | null = null,
): ProjectReference => ({ id: "r", project_id: "p", kind, label, value, position: 0 });

const upper = (key: string) => key.toUpperCase();

describe("BLANK_REFERENCE_FORM", () => {
  it("is a purchase order with nothing entered", () => {
    expect(BLANK_REFERENCE_FORM).toEqual({ kind: "purchase_order", label: "", value: "" });
  });
});

describe("REFERENCE_KINDS", () => {
  it("lists the eight kinds, custom included", () => {
    expect(REFERENCE_KINDS).toHaveLength(8);
    expect(REFERENCE_KINDS).toContain("custom");
    expect(REFERENCE_KINDS[0]).toBe("purchase_order");
  });
});

describe("referenceToFormValues", () => {
  it("turns a missing label into an empty one", () => {
    expect(referenceToFormValues(reference("contract", "C-1"))).toEqual({
      kind: "contract",
      label: "",
      value: "C-1",
    });
  });

  it("keeps a custom reference's label, for Edit and for Duplicate", () => {
    expect(referenceToFormValues(reference("custom", "CC-77", "Cost center"))).toEqual({
      kind: "custom",
      label: "Cost center",
      value: "CC-77",
    });
  });
});

describe("withKind", () => {
  it("shows an empty label when changing to custom", () => {
    expect(withKind({ kind: "contract", label: "", value: "C-1" }, "custom")).toEqual({
      kind: "custom",
      label: "",
      value: "C-1",
    });
  });

  it("discards the label when leaving custom and keeps the value", () => {
    expect(withKind({ kind: "custom", label: "Cost center", value: "X" }, "contract")).toEqual(
      {
        kind: "contract",
        label: "",
        value: "X",
      },
    );
  });

  it("keeps the label between two custom values", () => {
    expect(
      withKind({ kind: "custom", label: "Cost center", value: "X" }, "custom").label,
    ).toBe("Cost center");
  });
});

describe("toReferenceInput", () => {
  it("trims, and sends no label for a typed kind", () => {
    expect(
      toReferenceInput({ kind: "purchase_order", label: "left over", value: " PO-1 " }),
    ).toEqual({
      kind: "purchase_order",
      label: null,
      value: "PO-1",
    });
  });

  it("sends a custom reference's trimmed label", () => {
    expect(
      toReferenceInput({ kind: "custom", label: " Cost center ", value: "CC-77" }),
    ).toEqual({
      kind: "custom",
      label: "Cost center",
      value: "CC-77",
    });
  });
});

describe("referenceName", () => {
  it("is the kind's translated name for a typed kind", () => {
    expect(referenceName(reference("purchase_order", "PO-1"), upper)).toBe("PURCHASE ORDER");
  });

  it("is a custom reference's own label, never translated", () => {
    expect(referenceName(reference("custom", "X", "Cost center"), upper)).toBe("Cost center");
  });
});

describe("MAX_PROJECT_REFERENCES", () => {
  it("matches the API's limit", () => {
    expect(MAX_PROJECT_REFERENCES).toBe(50);
  });
});
