import { zodResolver } from "@hookform/resolvers/zod";
import { Check, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addServiceLine, updateServiceLine } from "@/api/projects";
import { listUsers } from "@/api/users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { formatMoney, formatQuantity, stripGrouping } from "@/lib/format";
import { type ServiceLineConsultant, UOM_LABELS, type Uom } from "@/types/project";
import type { User } from "@/types/user";

const UOM_VALUES = Object.keys(UOM_LABELS) as [Uom, ...Uom[]];
// Values may be pre-filled already comma-grouped (see formatQuantity/formatMoney) —
// strip that before checking shape, same as on submit.
const DECIMAL_PATTERN = /^\d+(\.\d+)?$/;
// Matches CompaniesTable's search debounce (see
// docs/requirements/company.md#companies-list-screen) — same rationale, applied here
// to the consultant picker's server-side search.
const SEARCH_DEBOUNCE_MS = 300;

const _shapeSchema = z.object({
  name: z.string(),
  quantity: z.string(),
  uom: z.enum(UOM_VALUES),
  unit_price: z.string(),
  user_ids: z.array(z.string()),
});
type FormValues = z.infer<typeof _shapeSchema>;

const BLANK_VALUES: FormValues = {
  name: "",
  quantity: "",
  uom: "hours",
  unit_price: "",
  user_ids: [],
};

interface ServiceLineFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  /** Present when editing an existing row in place; absent for add/duplicate-as-new. */
  serviceLineId?: string;
  initialValues?: Partial<FormValues>;
  /** Full consultant objects for `initialValues.user_ids` (Edit/Duplicate) — carried
   * separately since the form field itself only needs bare ids, but the picker needs
   * `full_name` to render each pre-selected consultant's chip without an extra fetch. */
  initialConsultants?: ServiceLineConsultant[];
  onSaved: () => void;
  /** The project's invoicing currency's decimal precision, for formatting the
   * pre-filled Unit price value — see docs/architecture/database.md#currencies. */
  minorUnit: number | null | undefined;
}

export function ServiceLineFormDialog({
  open,
  onOpenChange,
  projectId,
  serviceLineId,
  initialValues,
  initialConsultants,
  onSaved,
  minorUnit,
}: ServiceLineFormDialogProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedConsultants, setSelectedConsultants] = useState<ServiceLineConsultant[]>([]);
  const [consultantPopoverOpen, setConsultantPopoverOpen] = useState(false);
  const [consultantSearch, setConsultantSearch] = useState("");
  const [consultantResults, setConsultantResults] = useState<User[]>([]);

  const schema = useMemo(
    () =>
      z.object({
        name: z.string(),
        quantity: z.string().refine(
          (v) => DECIMAL_PATTERN.test(stripGrouping(v)) && Number(stripGrouping(v)) > 0,
          { message: t("Quantity must be greater than zero") },
        ),
        uom: z.enum(UOM_VALUES),
        unit_price: z.string().refine(
          (v) => DECIMAL_PATTERN.test(stripGrouping(v)) && Number(stripGrouping(v)) >= 0,
          { message: t("Unit price must not be negative") },
        ),
        user_ids: z.array(z.string()),
      }),
    [t],
  );

  // Pre-filled values (Edit/Duplicate) are formatted the same way the read-only
  // Service Lines table displays them — trimmed decimals for quantity, fixed
  // currency-precision grouping for unit price — so the modal doesn't show a
  // different, rawer number than what the user just saw in the table. Stripped back
  // to a plain decimal on submit (see onSubmit below).
  function formatInitialValues(values?: Partial<FormValues>): Partial<FormValues> {
    if (!values) return {};
    return {
      ...values,
      quantity: values.quantity !== undefined ? formatQuantity(values.quantity) : undefined,
      unit_price:
        values.unit_price !== undefined ? formatMoney(values.unit_price, minorUnit) : undefined,
    };
  }

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...BLANK_VALUES, ...formatInitialValues(initialValues) },
  });

  useEffect(() => {
    if (open) {
      setFormError(null);
      reset({ ...BLANK_VALUES, ...formatInitialValues(initialValues) });
      setSelectedConsultants(initialConsultants ?? []);
      setConsultantSearch("");
      setConsultantResults([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Server-side search (see docs/requirements/project.md#service-lines) — only fetches
  // while the picker is open. Instant on open (empty query), debounced while typing.
  useEffect(() => {
    if (!consultantPopoverOpen) return;
    let cancelled = false;
    const handle = setTimeout(
      () => {
        listUsers({
          role: "consultant",
          search: consultantSearch || undefined,
          is_active: true,
        })
          .then((response) => {
            if (!cancelled) setConsultantResults(response.items);
          })
          .catch(() => {
            if (!cancelled) setConsultantResults([]);
          });
      },
      consultantSearch ? SEARCH_DEBOUNCE_MS : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [consultantPopoverOpen, consultantSearch]);

  const uom = watch("uom");

  function toggleConsultant(consultant: ServiceLineConsultant) {
    setSelectedConsultants((prev) => {
      const next = prev.some((c) => c.id === consultant.id)
        ? prev.filter((c) => c.id !== consultant.id)
        : [...prev, consultant];
      setValue(
        "user_ids",
        next.map((c) => c.id),
      );
      return next;
    });
  }

  async function onSubmit(values: FormValues) {
    setFormError(null);
    const payload = {
      ...values,
      name: values.name.trim() || null,
      quantity: stripGrouping(values.quantity),
      unit_price: stripGrouping(values.unit_price),
    };
    try {
      if (serviceLineId) {
        await updateServiceLine(projectId, serviceLineId, payload);
      } else {
        await addServiceLine(projectId, payload);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save service line."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {serviceLineId ? t("Edit service line") : t("Add service line")}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="name">{t("Name")}</Label>
            <Input id="name" {...register("name")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="quantity">{t("Quantity")}</Label>
              <Input id="quantity" inputMode="decimal" {...register("quantity")} />
              {errors.quantity && (
                <p className="text-sm text-destructive">{errors.quantity.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="uom">{t("Unit")}</Label>
              <Select value={uom} onValueChange={(value) => setValue("uom", value as Uom)}>
                <SelectTrigger id="uom">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {UOM_VALUES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {t(UOM_LABELS[value])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="unit_price">{t("Unit price")}</Label>
            <Input id="unit_price" inputMode="decimal" {...register("unit_price")} />
            {errors.unit_price && (
              <p className="text-sm text-destructive">{errors.unit_price.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label>{t("Consultants")}</Label>
            <Popover open={consultantPopoverOpen} onOpenChange={setConsultantPopoverOpen}>
              <PopoverTrigger asChild>
                <Button type="button" variant="outline" className="w-fit">
                  {t("Select consultants…")}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-72 p-0" align="start">
                <Command shouldFilter={false}>
                  <CommandInput
                    placeholder={t("Search consultants…")}
                    value={consultantSearch}
                    onValueChange={setConsultantSearch}
                  />
                  <CommandList>
                    <CommandEmpty>{t("No consultants found.")}</CommandEmpty>
                    <CommandGroup>
                      {consultantResults.map((consultant) => {
                        const isSelected = selectedConsultants.some(
                          (c) => c.id === consultant.id,
                        );
                        return (
                          <CommandItem
                            key={consultant.id}
                            value={consultant.id}
                            onSelect={() => toggleConsultant(consultant)}
                          >
                            <span className="flex h-4 w-4 items-center justify-center">
                              {isSelected && <Check className="h-4 w-4" aria-hidden="true" />}
                            </span>
                            {consultant.full_name}
                          </CommandItem>
                        );
                      })}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>

            {selectedConsultants.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedConsultants.map((consultant) => (
                  <Badge key={consultant.id} variant="secondary" className="gap-1 pr-1">
                    {consultant.full_name}
                    <button
                      type="button"
                      onClick={() => toggleConsultant(consultant)}
                      className="rounded-full p-0.5 hover:bg-background"
                    >
                      <X className="h-3 w-3" aria-hidden="true" />
                      <span className="sr-only">
                        {t("Remove {{name}}", { name: consultant.full_name })}
                      </span>
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {formError && <p className="text-sm text-destructive">{formError}</p>}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner />}
              {isSubmitting ? t("Saving…", { ns: "common" }) : t("Save", { ns: "common" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
