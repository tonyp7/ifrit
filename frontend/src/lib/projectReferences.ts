import type { ProjectReference, ProjectReferenceInput, ReferenceKind } from "@/types/project";
import { REFERENCE_KIND_LABELS } from "@/types/project";

// The pure rules behind the project references dialog and table, kept apart from the
// components so they can be tested without a browser.

/** A guardrail, matching the API's limit: far above what a real project carries. */
export const MAX_PROJECT_REFERENCES = 50;

/** Every kind, in the order the type picker lists them. */
export const REFERENCE_KINDS = Object.keys(REFERENCE_KIND_LABELS) as ReferenceKind[];

/** What the dialog edits. `label` is only meaningful for `custom` and is "" otherwise, so
 * its input stays controlled. */
export interface ReferenceFormValues {
  kind: ReferenceKind;
  label: string;
  value: string;
}

/** A new reference is a purchase order, whatever the project already has: a predictable
 * default, with the other kinds one choice away. */
export const BLANK_REFERENCE_FORM: ReferenceFormValues = {
  kind: "purchase_order",
  label: "",
  value: "",
};

/** The dialog's starting values for an existing reference (Edit, Duplicate). */
export function referenceToFormValues(reference: ProjectReference): ReferenceFormValues {
  return { kind: reference.kind, label: reference.label ?? "", value: reference.value };
}

/** The values with their kind changed. Leaving `custom` discards the label (a typed kind
 * has no label), and the value is kept. */
export function withKind(
  values: ReferenceFormValues,
  kind: ReferenceKind,
): ReferenceFormValues {
  return { ...values, kind, label: kind === "custom" ? values.label : "" };
}

/** What is sent: trimmed, and no label on a typed kind. */
export function toReferenceInput(values: ReferenceFormValues): ProjectReferenceInput {
  return {
    kind: values.kind,
    label: values.kind === "custom" ? values.label.trim() : null,
    value: values.value.trim(),
  };
}

/** What the "Reference Name" column shows: a custom reference's own label, otherwise the
 * kind's name. `translate` is the caller's `t`. */
export function referenceName(
  reference: Pick<ProjectReference, "kind" | "label">,
  translate: (key: string) => string,
): string {
  return reference.kind === "custom"
    ? (reference.label ?? "")
    : translate(REFERENCE_KIND_LABELS[reference.kind]);
}
