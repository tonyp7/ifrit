import { Plus, X } from "lucide-react";
import type { UseFormReturn } from "react-hook-form";
import { useFieldArray, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";

import type { InvoiceFormValues } from "@/components/invoices/invoiceForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { REFERENCE_KIND_LABELS, type ReferenceKind } from "@/types/project";

const KINDS = Object.keys(REFERENCE_KIND_LABELS) as ReferenceKind[];
// The API's limit, the same as a project's.
const MAX_REFERENCES = 50;

interface InvoiceReferencesFieldsProps {
  form: UseFormReturn<InvoiceFormValues>;
  disabled?: boolean;
}

/**
 * The references printed on the invoice, copied from the project and edited here without
 * touching it. A kind the project has several values of starts empty with a picker, since
 * most e-invoicing targets take one per invoice.
 */
export function InvoiceReferencesFields({ form, disabled }: InvoiceReferencesFieldsProps) {
  const { t } = useTranslation(["invoices", "projects", "common"]);
  const {
    control,
    register,
    setValue,
    formState: { errors },
  } = form;
  const { fields, append, remove } = useFieldArray({ control, name: "references" });
  const rows = useWatch({ control, name: "references" });
  const set = { shouldDirty: true, shouldValidate: true } as const;

  return (
    <fieldset className="flex flex-col gap-3 rounded-md border p-4" disabled={disabled}>
      <legend className="px-1 text-sm font-medium">{t("References")}</legend>
      {fields.length === 0 && (
        <p className="text-muted-foreground text-sm">{t("No references on this invoice.")}</p>
      )}
      {fields.map((field, index) => {
        const row = rows[index] ?? field;
        const rowErrors = errors.references?.[index];
        return (
          <div key={field.id} className="flex flex-wrap items-start gap-2">
            <div className="flex w-full flex-col gap-1 sm:w-44">
              <Label htmlFor={`reference_kind_${index}`} className="sr-only">
                {t("Reference")}
              </Label>
              <Select
                value={row.kind}
                disabled={disabled}
                onValueChange={(value) => {
                  setValue(`references.${index}.kind`, value as ReferenceKind, set);
                  setValue(`references.${index}.options`, [], set);
                }}
              >
                <SelectTrigger id={`reference_kind_${index}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((kind) => (
                    <SelectItem key={kind} value={kind}>
                      {t(REFERENCE_KIND_LABELS[kind], { ns: "projects" })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {row.kind === "custom" && (
              <div className="flex w-full flex-col gap-1 sm:w-36">
                <Input
                  aria-label={t("Label")}
                  placeholder={t("Label")}
                  maxLength={100}
                  aria-invalid={!!rowErrors?.label}
                  {...register(`references.${index}.label`)}
                />
                {rowErrors?.label && (
                  <p className="text-destructive text-sm">{rowErrors.label.message}</p>
                )}
              </div>
            )}
            <div className="flex min-w-40 flex-1 flex-col gap-1">
              {row.options.length > 0 ? (
                <Select
                  value={row.value || undefined}
                  disabled={disabled}
                  onValueChange={(value) => setValue(`references.${index}.value`, value, set)}
                >
                  <SelectTrigger aria-label={t("Value")} aria-invalid={!!rowErrors?.value}>
                    <SelectValue placeholder={t("Which one is this invoice for?")} />
                  </SelectTrigger>
                  <SelectContent>
                    {row.options.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  aria-label={t("Value")}
                  maxLength={255}
                  aria-invalid={!!rowErrors?.value}
                  {...register(`references.${index}.value`)}
                />
              )}
              {rowErrors?.value && (
                <p className="text-destructive text-sm">{rowErrors.value.message}</p>
              )}
            </div>
            {!disabled && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 w-9 p-0"
                aria-label={t("Remove reference")}
                onClick={() => remove(index)}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        );
      })}
      {!disabled && fields.length < MAX_REFERENCES && (
        <div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              append({ kind: "purchase_order", label: "", value: "", options: [] })
            }
          >
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("Add reference")}
          </Button>
        </div>
      )}
    </fieldset>
  );
}
