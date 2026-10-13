import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addBillingMilestone, updateBillingMilestone } from "@/api/projects";
import { DueDatePicker } from "@/components/projects/DueDatePicker";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import {
  BLANK_MILESTONE_FORM,
  fitsCurrency,
  isDecimalInput,
  type MilestoneFormValues,
  percentFromValueInput,
  valueFromPercentInput,
} from "@/lib/billingMilestones";
import { stripGrouping } from "@/lib/format";
import { milestoneDecimals } from "@/lib/milestoneMath";

interface BillingMilestoneFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  /** Present when editing an existing milestone in place; absent for add/duplicate. */
  milestoneId?: string;
  initialValues?: MilestoneFormValues;
  /** The project's contract value (sum of its service lines), the base of the %. */
  contractValue: string;
  minorUnit: number | null | undefined;
  onSaved: () => void;
}

export function BillingMilestoneFormDialog({
  open,
  onOpenChange,
  projectId,
  milestoneId,
  initialValues,
  contractValue,
  minorUnit,
  onSaved,
}: BillingMilestoneFormDialogProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [formError, setFormError] = useState<string | null>(null);
  // With no contract value there is nothing to take a percentage of: only the value can be
  // entered.
  const hasContractValue = Number(contractValue) !== 0;

  const schema = useMemo(
    () =>
      z.object({
        description: z.string().refine((v) => v.trim().length > 0, {
          message: t("Description is required"),
        }),
        dueDate: z.string().nullable(),
        percent: z.string(),
        value: z
          .string()
          .refine(isDecimalInput, { message: t("Value must be a number of zero or more") })
          .refine((v) => !isDecimalInput(v) || fitsCurrency(v, minorUnit), {
            message: t("Value can have at most {{count}} decimals", {
              count: milestoneDecimals(minorUnit),
            }),
          }),
      }),
    [t, minorUnit],
  );

  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<MilestoneFormValues>({
    resolver: zodResolver(schema),
    defaultValues: initialValues ?? BLANK_MILESTONE_FORM,
  });

  // Each time the dialog opens it starts from a clean slate: the error message is state of
  // this component, cleared while rendering by comparing with the previous `open`; the form
  // library's own state is reset in an effect.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setFormError(null);
  }

  useEffect(() => {
    if (open) reset(initialValues ?? BLANK_MILESTONE_FORM);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const dueDate = useWatch({ control, name: "dueDate" });
  const percent = useWatch({ control, name: "percent" });
  const value = useWatch({ control, name: "value" });

  // Whichever of % and Value was typed in last is in charge; the other follows it. Only
  // the value is ever saved.
  function handlePercentChange(input: string) {
    setValue("percent", input);
    setValue("value", valueFromPercentInput(input, contractValue, minorUnit));
  }

  function handleValueChange(input: string) {
    setValue("value", input);
    setValue("percent", percentFromValueInput(input, contractValue));
  }

  async function onSubmit(values: MilestoneFormValues) {
    setFormError(null);
    const payload = {
      description: values.description.trim(),
      due_date: values.dueDate,
      value: stripGrouping(values.value).trim(),
    };
    try {
      if (milestoneId) {
        await updateBillingMilestone(projectId, milestoneId, payload);
      } else {
        await addBillingMilestone(projectId, payload);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : t("Failed to save billing milestone."),
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {milestoneId ? t("Edit billing milestone") : t("Add billing milestone")}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="milestone-description">{t("Description")}</Label>
            <Input
              id="milestone-description"
              aria-invalid={!!errors.description}
              {...register("description")}
            />
            {errors.description && (
              <p className="text-destructive text-sm">{errors.description.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="milestone-due-date">{t("Due date")}</Label>
            <DueDatePicker
              id="milestone-due-date"
              value={dueDate}
              onChange={(next) => setValue("dueDate", next)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="milestone-percent">%</Label>
              <Input
                id="milestone-percent"
                inputMode="decimal"
                disabled={!hasContractValue}
                value={percent}
                onChange={(e) => handlePercentChange(e.target.value)}
              />
              {!hasContractValue && (
                <p className="text-muted-foreground text-sm">
                  {t("Add service lines to enter a percentage.")}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="milestone-value">{t("Value")}</Label>
              <Input
                id="milestone-value"
                inputMode="decimal"
                aria-invalid={!!errors.value}
                value={value}
                onChange={(e) => handleValueChange(e.target.value)}
              />
              {errors.value && (
                <p className="text-destructive text-sm">{errors.value.message}</p>
              )}
            </div>
          </div>

          {formError && <p className="text-destructive text-sm">{formError}</p>}

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
