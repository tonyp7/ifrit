import {
  closestCenter,
  DndContext,
  type Announcements,
  type DragEndEvent,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  type UniqueIdentifier,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import type { UseFormReturn } from "react-hook-form";
import { useFieldArray, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { blankTax, type InvoiceFormValues } from "@/components/invoices/invoiceForm";
import { TaxLabelCombobox } from "@/components/invoices/TaxLabelCombobox";
import { SortableRow } from "@/components/SortableRow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatMoney } from "@/lib/format";
import { subtotal } from "@/lib/invoiceMath";
import {
  computeTaxes,
  displayRate,
  isTaxBaseMode,
  labelChange,
  TAX_BASE_MODE_LABELS,
  totalWithTaxes,
} from "@/lib/invoiceTaxes";
import { milestoneDecimals, roundDecimal } from "@/lib/milestoneMath";
import type { InvoiceTax, TaxBaseMode } from "@/types/invoice";

// The API's limit.
const MAX_TAXES = 20;

interface InvoiceTaxesTableProps {
  form: UseFormReturn<InvoiceFormValues>;
  currencyCode: string | null;
  minorUnit: number | null;
  disabled?: boolean;
  /** An issued or void invoice: its tax rows and total exactly as they were stored. */
  stored?: { taxes: InvoiceTax[]; total: string } | null;
}

/**
 * The tax rows under the subtotal, and the total. Each row's base, and whichever of rate
 * and amount was not typed, are worked out on every render from the lines and the rows
 * above, so editing a line or moving a row recomputes everything at once.
 */
export function InvoiceTaxesTable({
  form,
  currencyCode,
  minorUnit,
  disabled,
  stored,
}: InvoiceTaxesTableProps) {
  const { t } = useTranslation(["invoices", "common"]);
  const {
    control,
    register,
    setValue,
    formState: { errors },
  } = form;
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: "taxes",
    keyName: "fieldId",
  });
  const lines = useWatch({ control, name: "lines" });
  const taxes = useWatch({ control, name: "taxes" });
  const sortable = !disabled && fields.length > 1;

  const sensors = useSensors(
    useSensor(MouseSensor),
    // A short press before a touch drag starts, so a swipe across the table still scrolls.
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const describe = (id: UniqueIdentifier | undefined) =>
    taxes.find((tax) => tax.key === id)?.label || t("a tax");
  const announcements: Announcements = {
    onDragStart: ({ active }) => t("Picked up {{name}}.", { name: describe(active.id) }),
    onDragOver: ({ active, over }) =>
      over
        ? t("{{name}} was moved over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : t("{{name}} is no longer over a tax.", { name: describe(active.id) }),
    onDragEnd: ({ active, over }) =>
      over
        ? t("{{name}} was dropped over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : t("{{name}} was dropped.", { name: describe(active.id) }),
    onDragCancel: ({ active }) =>
      t("Reordering was cancelled. {{name}} was dropped.", { name: describe(active.id) }),
  };

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return;
    const from = fields.findIndex((field) => field.key === active.id);
    const to = fields.findIndex((field) => field.key === over.id);
    if (from >= 0 && to >= 0) move(from, to);
  }

  const lineSubtotal = subtotal(lines, minorUnit);
  const computed = computeTaxes(lineSubtotal, taxes, minorUnit);
  const total = stored ? stored.total : totalWithTaxes(lineSubtotal, computed, minorUnit);
  const money = (value: string) => formatMoney(value, minorUnit);

  function setRow<K extends "label" | "base_mode" | "rate" | "amount" | "amount_set_by_hand">(
    index: number,
    name: K,
    value: InvoiceFormValues["taxes"][number][K],
  ) {
    setValue(`taxes.${index}.${name}`, value as never, { shouldDirty: true });
  }

  function pickLabel(index: number, label: string, preset: boolean) {
    const patch = labelChange(label, preset);
    setRow(index, "label", patch.label);
    if (patch.rate !== undefined) setRow(index, "rate", patch.rate);
    if (patch.amount_set_by_hand !== undefined) {
      setRow(index, "amount_set_by_hand", patch.amount_set_by_hand);
    }
  }

  // Back to rate-driven, starting from the rate the hand-set amount worked out to when
  // it is one that could have been typed.
  function backToRate(index: number) {
    const derived = computed[index]?.rate;
    if (
      derived !== null &&
      derived !== undefined &&
      Number(derived) >= 0 &&
      Number(derived) <= 100
    ) {
      setRow(index, "rate", displayRate(derived));
    }
    setRow(index, "amount_set_by_hand", false);
    setRow(index, "amount", "");
  }

  const totalRow = (
    <div className="flex justify-end">
      <dl className="grid grid-cols-[auto_auto] gap-x-6 text-sm">
        <dt className="font-medium">
          {currencyCode ? t("Total ({{currency}})", { currency: currencyCode }) : t("Total")}
        </dt>
        <dd className="text-right font-medium tabular-nums" data-testid="total">
          {money(total)}
        </dd>
      </dl>
    </div>
  );

  if (stored) {
    return (
      <div className="flex flex-col gap-3">
        {stored.taxes.length > 0 && (
          <div className="rounded-md border">
            <Table className="min-w-[40rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Tax")}</TableHead>
                  <TableHead>{t("Applies to")}</TableHead>
                  <TableHead className="w-32 text-right">{t("Rate")}</TableHead>
                  <TableHead className="w-36 text-right">{t("Amount")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stored.taxes.map((tax, index) => (
                  <TableRow key={index}>
                    <TableCell>{tax.label}</TableCell>
                    <TableCell>
                      <div>{t(TAX_BASE_MODE_LABELS[tax.base_mode])}</div>
                      <div className="text-muted-foreground text-xs">
                        {t("on {{base}}", { base: money(tax.base_amount) })}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {tax.rate === null
                        ? "—"
                        : `${tax.amount_set_by_hand ? "≈ " : ""}${displayRate(tax.rate)} %`}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {money(tax.amount)}
                      {tax.amount_set_by_hand && (
                        <div className="text-muted-foreground text-xs">{t("Set by hand")}</div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        {totalRow}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {fields.length > 0 && (
        <div className="rounded-md border">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis]}
            onDragEnd={handleDragEnd}
            accessibility={{
              announcements,
              screenReaderInstructions: {
                draggable: t(
                  "To pick up a tax, press Space or Enter. Use the arrow keys to move it, Space or Enter to drop it, or Escape to cancel.",
                ),
              },
            }}
          >
            <Table className="min-w-[44rem]">
              <TableHeader>
                <TableRow>
                  {sortable && <TableHead className="w-10" />}
                  <TableHead>{t("Tax")}</TableHead>
                  <TableHead className="w-56">{t("Applies to")}</TableHead>
                  <TableHead className="w-32">{t("Rate")}</TableHead>
                  <TableHead className="w-40">{t("Amount")}</TableHead>
                  {!disabled && <TableHead className="w-10" />}
                </TableRow>
              </TableHeader>
              <TableBody>
                <SortableContext
                  items={fields.map((field) => field.key)}
                  strategy={verticalListSortingStrategy}
                >
                  {fields.map((field, index) => {
                    const tax = taxes[index] ?? field;
                    const result = computed[index];
                    const rowErrors = errors.taxes?.[index];
                    const amountValue = tax.amount_set_by_hand
                      ? tax.amount
                      : result?.amount !== null && result?.amount !== undefined
                        ? (roundDecimal(result.amount, milestoneDecimals(minorUnit)) ?? "")
                        : "";
                    return (
                      <SortableRow
                        key={field.key}
                        id={field.key}
                        description={tax.label || t("a tax")}
                        sortable={sortable}
                      >
                        <TableCell className="align-top">
                          <TaxLabelCombobox
                            value={tax.label}
                            invalid={!!rowErrors?.label}
                            disabled={disabled}
                            onChange={(label, preset) => pickLabel(index, label, preset)}
                          />
                          {rowErrors?.label && (
                            <p className="text-destructive text-sm">
                              {rowErrors.label.message}
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="align-top">
                          {index === 0 ? (
                            <p className="flex h-9 items-center text-sm">
                              {t(TAX_BASE_MODE_LABELS.subtotal)}
                            </p>
                          ) : (
                            <Select
                              value={tax.base_mode}
                              disabled={disabled}
                              // A dropdown that mounts inside the form, as this one does
                              // when its row moves down from first place, can report an
                              // empty value; only a real choice is kept.
                              onValueChange={(value) => {
                                if (isTaxBaseMode(value)) setRow(index, "base_mode", value);
                              }}
                            >
                              <SelectTrigger aria-label={t("Applies to")}>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {(Object.keys(TAX_BASE_MODE_LABELS) as TaxBaseMode[]).map(
                                  (mode) => (
                                    <SelectItem key={mode} value={mode}>
                                      {t(TAX_BASE_MODE_LABELS[mode])}
                                    </SelectItem>
                                  ),
                                )}
                              </SelectContent>
                            </Select>
                          )}
                          {result && (
                            <p className="text-muted-foreground mt-1 text-xs tabular-nums">
                              {t("on {{base}}", { base: money(result.base) })}
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="align-top">
                          {tax.amount_set_by_hand ? (
                            <p
                              className="flex h-9 items-center justify-end text-sm tabular-nums"
                              data-testid="derived-rate"
                            >
                              {result?.rate === null || result?.rate === undefined
                                ? "—"
                                : `≈ ${displayRate(result.rate)} %`}
                            </p>
                          ) : (
                            <div className="flex items-center gap-1">
                              <Input
                                aria-label={t("Rate")}
                                inputMode="decimal"
                                className="text-right tabular-nums"
                                disabled={disabled}
                                aria-invalid={!!rowErrors?.rate}
                                {...register(`taxes.${index}.rate`)}
                              />
                              <span className="text-muted-foreground text-sm">%</span>
                            </div>
                          )}
                          {rowErrors?.rate && (
                            <p className="text-destructive text-sm">
                              {rowErrors.rate.message}
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="align-top">
                          <Input
                            aria-label={t("Amount")}
                            inputMode="decimal"
                            className="text-right tabular-nums"
                            disabled={disabled}
                            aria-invalid={!!rowErrors?.amount}
                            value={amountValue}
                            onChange={(event) => {
                              setRow(index, "amount", event.target.value);
                              setRow(index, "amount_set_by_hand", true);
                            }}
                          />
                          {tax.amount_set_by_hand && (
                            <div className="mt-1 flex items-center justify-end gap-1">
                              <Badge variant="secondary" className="gap-1 font-normal">
                                <Pencil className="h-3 w-3" aria-hidden="true" />
                                {t("Set by hand")}
                              </Badge>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0"
                                aria-label={t("Calculate from the rate again")}
                                title={t("Calculate from the rate again")}
                                disabled={disabled}
                                onClick={() => backToRate(index)}
                              >
                                <RotateCcw className="h-3 w-3" aria-hidden="true" />
                              </Button>
                            </div>
                          )}
                          {rowErrors?.amount && (
                            <p className="text-destructive text-sm">
                              {rowErrors.amount.message}
                            </p>
                          )}
                        </TableCell>
                        {!disabled && (
                          <TableCell className="align-top">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              aria-label={t("Delete tax")}
                              onClick={() => remove(index)}
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                            </Button>
                          </TableCell>
                        )}
                      </SortableRow>
                    );
                  })}
                </SortableContext>
              </TableBody>
            </Table>
          </DndContext>
        </div>
      )}
      {errors.taxes?.message && (
        <p className="text-destructive text-sm">{errors.taxes.message}</p>
      )}
      {!disabled && fields.length < MAX_TAXES && (
        <div>
          <Button type="button" variant="outline" size="sm" onClick={() => append(blankTax())}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("Add tax")}
          </Button>
        </div>
      )}
      {totalRow}
    </div>
  );
}
