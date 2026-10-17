import { z } from "zod";

import { addressToFields, type PartyFormValues } from "@/lib/invoiceParties";
import { payeeFormFromInvoice, toInvoicePayee } from "@/lib/invoicePayee";
import {
  rowsFromInvoice,
  toInvoiceReferences,
  type InvoiceReferenceRow,
} from "@/lib/invoiceReferences";
import { PERIOD_PRESETS, type PeriodPreset } from "@/lib/invoicePeriods";
import {
  BLANK_ADDRESS_FIELDS,
  compactIban,
  isValidBic,
  isValidIban,
  missingBankAddressFields,
  toBankAddress,
  type PayeeAccountFormValues,
} from "@/lib/payeeAccounts";
import {
  PAYMENT_TERMS,
  type InvoiceDetail,
  type InvoiceInput,
  type PaymentTerms,
} from "@/types/invoice";
import { REFERENCE_KIND_LABELS, type ReferenceKind, type Uom } from "@/types/project";

export interface InvoiceLineFormValues {
  /** Stable row identity for drag and drop and React keys; never sent. */
  key: string;
  description: string;
  quantity: string;
  uom: Uom;
  unit_price: string;
}

export interface InvoiceFormValues {
  project_id: string;
  bill_from: PartyFormValues;
  bill_to: PartyFormValues;
  /** The preset the period was filled from; cleared once the range is edited by hand. */
  period_preset: PeriodPreset | null;
  period_start: string | null;
  period_end: string | null;
  service_line_ids: string[];
  payment_terms: PaymentTerms | null;
  due_date: string | null;
  payee: PayeeAccountFormValues | null;
  references: InvoiceReferenceRow[];
  lines: InvoiceLineFormValues[];
}

let nextKey = 0;
export function newLineKey(): string {
  nextKey += 1;
  return `line-${nextKey}`;
}

export const BLANK_PARTY: PartyFormValues = { name: "", address: BLANK_ADDRESS_FIELDS };

export const BLANK_INVOICE_FORM: InvoiceFormValues = {
  project_id: "",
  bill_from: BLANK_PARTY,
  bill_to: BLANK_PARTY,
  period_preset: null,
  period_start: null,
  period_end: null,
  service_line_ids: [],
  payment_terms: null,
  due_date: null,
  payee: null,
  references: [],
  lines: [],
};

export function blankLine(): InvoiceLineFormValues {
  return { key: newLineKey(), description: "", quantity: "", uom: "hours", unit_price: "" };
}

// Free text while typing, checked on save: the same limits as the API's.
const QUANTITY = /^\d{1,7}(\.\d{1,5})?$/;
const UNIT_PRICE = /^-?\d{1,10}(\.\d{1,4})?$/;

type Translate = (key: string) => string;

/** Built inside the form so the messages go through t(); mirrors the API's rules. */
export function invoiceSchema(t: Translate) {
  const text = z.string();
  const address = z.object({
    line1: text,
    line2: text,
    line3: text,
    city: text,
    postal_zone: text,
    country_subdivision: text,
    country_code: text,
  });
  const party = z.object({
    name: z
      .string()
      .trim()
      .min(1, t("A name is required"))
      .max(255, t("At most 255 characters")),
    address,
  });
  const addressMessages = {
    line1: t("Line 1 is required"),
    city: t("City is required"),
    country_code: t("A country is required"),
  };
  return z
    .object({
      project_id: z.string().min(1, t("Choose a project")),
      bill_from: party,
      bill_to: party,
      period_preset: z.enum(PERIOD_PRESETS as [PeriodPreset, ...PeriodPreset[]]).nullable(),
      period_start: z.string().nullable(),
      period_end: z.string().nullable(),
      service_line_ids: z.array(z.string()),
      payment_terms: z.enum(PAYMENT_TERMS as [PaymentTerms, ...PaymentTerms[]]).nullable(),
      due_date: z.string().nullable(),
      payee: z
        .object({
          payment_means_code: z.enum(["30", "42", "58"]),
          account_scheme: z.enum(["iban", "other"]),
          account_identifier: z.string().trim().min(1, t("Account identifier is required")),
          account_name: text,
          currency_code: z.string().min(1, t("Currency is required")),
          bic: text.refine((value) => !value.trim() || isValidBic(value), {
            message: t("A BIC is 8 or 11 letters or digits"),
          }),
          bank_name: text,
          bank_address: address,
          is_primary: z.boolean(),
        })
        .nullable(),
      references: z.array(
        z.object({
          kind: z.enum(
            Object.keys(REFERENCE_KIND_LABELS) as [ReferenceKind, ...ReferenceKind[]],
          ),
          label: text,
          value: text,
          options: z.array(z.string()),
        }),
      ),
      lines: z
        .array(
          z.object({
            key: z.string(),
            description: z
              .string()
              .trim()
              .min(1, t("A description is required"))
              .max(500, t("At most 500 characters")),
            quantity: z
              .string()
              .trim()
              .regex(QUANTITY, t("Zero or more, with up to 5 decimals")),
            uom: z.enum(["hours", "days", "ea"]),
            unit_price: z
              .string()
              .trim()
              .regex(UNIT_PRICE, t("A number with up to 4 decimals")),
          }),
        )
        .max(200, t("An invoice has at most 200 lines")),
    })
    .superRefine((data, ctx) => {
      for (const side of ["bill_from", "bill_to"] as const) {
        for (const name of missingBankAddressFields(data[side].address)) {
          ctx.addIssue({
            code: "custom",
            path: [side, "address", name],
            message: addressMessages[name],
          });
        }
      }
      if (data.payee) {
        if (
          data.payee.account_scheme === "iban" &&
          !isValidIban(compactIban(data.payee.account_identifier))
        ) {
          ctx.addIssue({
            code: "custom",
            path: ["payee", "account_identifier"],
            message: t("This is not a valid IBAN"),
          });
        }
        for (const name of missingBankAddressFields(data.payee.bank_address)) {
          ctx.addIssue({
            code: "custom",
            path: ["payee", "bank_address", name],
            message: addressMessages[name],
          });
        }
      }
      data.references.forEach((row, index) => {
        if (!row.value.trim()) {
          ctx.addIssue({
            code: "custom",
            path: ["references", index, "value"],
            message: t("Pick or type a value, or remove the reference"),
          });
        }
        if (row.kind === "custom" && !row.label.trim()) {
          ctx.addIssue({
            code: "custom",
            path: ["references", index, "label"],
            message: t("A label is required"),
          });
        }
      });
    });
}

/** The form's values as the API's write body. */
export function toInvoiceInput(values: InvoiceFormValues): InvoiceInput {
  return {
    project_id: values.project_id,
    bill_from: {
      name: values.bill_from.name.trim(),
      address: toBankAddress(values.bill_from.address),
    },
    bill_to: {
      name: values.bill_to.name.trim(),
      address: toBankAddress(values.bill_to.address),
    },
    period_start: values.period_start,
    period_end: values.period_end,
    payment_terms: values.payment_terms,
    due_date: values.payment_terms ? null : values.due_date,
    payee: values.payee ? toInvoicePayee(values.payee) : null,
    references: toInvoiceReferences(values.references),
    lines: values.lines.map((line) => ({
      description: line.description.trim(),
      quantity: line.quantity.trim(),
      uom: line.uom,
      unit_price: line.unit_price.trim(),
    })),
  };
}

/** A saved invoice as the form's values. The service line selection is a form choice that
 * is not saved, so the caller sets it from the project. */
export function fromInvoiceDetail(detail: InvoiceDetail): InvoiceFormValues {
  return {
    project_id: detail.project_id,
    bill_from: {
      name: detail.bill_from.name,
      address: addressToFields(detail.bill_from.address),
    },
    bill_to: { name: detail.bill_to.name, address: addressToFields(detail.bill_to.address) },
    period_preset: null,
    period_start: detail.period_start,
    period_end: detail.period_end,
    service_line_ids: [],
    payment_terms: detail.payment_terms,
    due_date: detail.due_date,
    payee: payeeFormFromInvoice(detail.payee),
    references: rowsFromInvoice(detail.references),
    lines: detail.lines.map((line) => ({
      key: newLineKey(),
      description: line.description,
      quantity: trimZeros(line.quantity),
      uom: line.uom,
      unit_price: trimZeros(line.unit_price),
    })),
  };
}

/** `152.50000` → `152.5`, `95.0000` → `95`: what a person types, not the column's scale. */
export function trimZeros(value: string): string {
  return value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;
}
