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
import { Plus, Trash2 } from "lucide-react";
import type { UseFormReturn } from "react-hook-form";
import { useFieldArray, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { blankLine, type InvoiceFormValues } from "@/components/invoices/invoiceForm";
import { SortableRow } from "@/components/SortableRow";
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
import { lineAmount, subtotal } from "@/lib/invoiceMath";
import { UOM_LABELS, type Uom } from "@/types/project";

const UOMS = Object.keys(UOM_LABELS) as Uom[];
// The API's limit.
const MAX_LINES = 200;

interface InvoiceLinesTableProps {
  form: UseFormReturn<InvoiceFormValues>;
  currencyCode: string | null;
  minorUnit: number | null;
  disabled?: boolean;
}

/**
 * The editable line items and their subtotal (the taxes and the total follow, below). Rows are reordered by drag and drop, and the
 * new order is part of the draft's unsaved edits: it is saved with the draft, not on drop.
 */
export function InvoiceLinesTable({
  form,
  currencyCode,
  minorUnit,
  disabled,
}: InvoiceLinesTableProps) {
  const { t } = useTranslation(["invoices", "projects", "common"]);
  const {
    control,
    register,
    setValue,
    formState: { errors },
  } = form;
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: "lines",
    keyName: "fieldId",
  });
  const lines = useWatch({ control, name: "lines" });
  const sortable = !disabled && fields.length > 1;

  const sensors = useSensors(
    useSensor(MouseSensor),
    // A short press before a touch drag starts, so a swipe across the table still scrolls.
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    // Arrow keys move the picked-up row by one position.
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const describe = (id: UniqueIdentifier | undefined) =>
    lines.find((line) => line.key === id)?.description || t("a line");
  const announcements: Announcements = {
    onDragStart: ({ active }) => t("Picked up {{name}}.", { name: describe(active.id) }),
    onDragOver: ({ active, over }) =>
      over
        ? t("{{name}} was moved over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : t("{{name}} is no longer over a line.", { name: describe(active.id) }),
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

  const total = subtotal(lines, minorUnit);
  const money = (value: string) =>
    `${formatMoney(value, minorUnit)}${currencyCode ? ` ${currencyCode}` : ""}`;

  return (
    <div className="flex flex-col gap-3">
      {/* The minimum width makes the table, inside the table primitive's own scrolling
          wrapper, scroll sideways on a narrow screen, never the page. */}
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
                "To pick up a line, press Space or Enter. Use the arrow keys to move it, Space or Enter to drop it, or Escape to cancel.",
              ),
            },
          }}
        >
          <Table className="min-w-[44rem]">
            <TableHeader>
              <TableRow>
                {sortable && <TableHead className="w-10" />}
                <TableHead>{t("Description")}</TableHead>
                <TableHead className="w-28">{t("Quantity")}</TableHead>
                <TableHead className="w-32">{t("Unit")}</TableHead>
                <TableHead className="w-32">{t("Unit price")}</TableHead>
                <TableHead className="w-36 text-right">{t("Amount")}</TableHead>
                {!disabled && <TableHead className="w-10" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              <SortableContext
                items={fields.map((field) => field.key)}
                strategy={verticalListSortingStrategy}
              >
                {fields.map((field, index) => {
                  const line = lines[index] ?? field;
                  const lineErrors = errors.lines?.[index];
                  const amount = lineAmount(line.quantity, line.unit_price, minorUnit);
                  return (
                    <SortableRow
                      key={field.key}
                      id={field.key}
                      description={line.description || t("a line")}
                      sortable={sortable}
                    >
                      <TableCell>
                        <Input
                          aria-label={t("Description")}
                          maxLength={500}
                          disabled={disabled}
                          aria-invalid={!!lineErrors?.description}
                          {...register(`lines.${index}.description`)}
                        />
                        {lineErrors?.description && (
                          <p className="text-destructive text-sm">
                            {lineErrors.description.message}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        <Input
                          aria-label={t("Quantity")}
                          inputMode="decimal"
                          className="text-right tabular-nums"
                          disabled={disabled}
                          aria-invalid={!!lineErrors?.quantity}
                          {...register(`lines.${index}.quantity`)}
                        />
                        {lineErrors?.quantity && (
                          <p className="text-destructive text-sm">
                            {lineErrors.quantity.message}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        <Select
                          value={line.uom}
                          disabled={disabled}
                          onValueChange={(value) =>
                            setValue(`lines.${index}.uom`, value as Uom, { shouldDirty: true })
                          }
                        >
                          <SelectTrigger aria-label={t("Unit")}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {UOMS.map((uom) => (
                              <SelectItem key={uom} value={uom}>
                                {t(UOM_LABELS[uom], { ns: "projects" })}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Input
                          aria-label={t("Unit price")}
                          inputMode="decimal"
                          className="text-right tabular-nums"
                          disabled={disabled}
                          aria-invalid={!!lineErrors?.unit_price}
                          {...register(`lines.${index}.unit_price`)}
                        />
                        {lineErrors?.unit_price && (
                          <p className="text-destructive text-sm">
                            {lineErrors.unit_price.message}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {amount === null ? "—" : formatMoney(amount, minorUnit)}
                      </TableCell>
                      {!disabled && (
                        <TableCell>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            aria-label={t("Delete line")}
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
              {fields.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-muted-foreground h-16 text-center">
                    {t("No lines yet. Generate them or add one.")}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </DndContext>
      </div>
      {errors.lines?.message && (
        <p className="text-destructive text-sm">{errors.lines.message}</p>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        {!disabled && fields.length < MAX_LINES ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => append(blankLine())}
          >
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("Add line")}
          </Button>
        ) : (
          <span />
        )}
        <dl className="grid grid-cols-[auto_auto] gap-x-6 gap-y-1 text-sm">
          <dt>{t("Subtotal")}</dt>
          <dd className="text-right tabular-nums" data-testid="subtotal">
            {money(total)}
          </dd>
        </dl>
      </div>
    </div>
  );
}
