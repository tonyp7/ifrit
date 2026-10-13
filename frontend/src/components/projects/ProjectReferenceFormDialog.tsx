import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addProjectReference, updateProjectReference } from "@/api/projects";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
  BLANK_REFERENCE_FORM,
  REFERENCE_KINDS,
  type ReferenceFormValues,
  toReferenceInput,
  withKind,
} from "@/lib/projectReferences";
import { REFERENCE_KIND_LABELS, type ReferenceKind } from "@/types/project";

interface ProjectReferenceFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  /** Present when editing an existing reference in place; absent for add/duplicate. */
  referenceId?: string;
  initialValues?: ReferenceFormValues;
  onSaved: () => void;
}

export function ProjectReferenceFormDialog({
  open,
  onOpenChange,
  projectId,
  referenceId,
  initialValues,
  onSaved,
}: ProjectReferenceFormDialogProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(
    () =>
      z
        .object({
          kind: z.enum(REFERENCE_KINDS as [ReferenceKind, ...ReferenceKind[]]),
          label: z.string(),
          value: z.string().refine((v) => v.trim().length > 0, {
            message: t("Value is required"),
          }),
        })
        .superRefine((values, ctx) => {
          if (values.kind === "custom" && values.label.trim().length === 0) {
            ctx.addIssue({ code: "custom", path: ["label"], message: t("Label is required") });
          }
        }),
    [t],
  );

  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<ReferenceFormValues>({
    resolver: zodResolver(schema),
    defaultValues: initialValues ?? BLANK_REFERENCE_FORM,
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
    if (open) reset(initialValues ?? BLANK_REFERENCE_FORM);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const kind = useWatch({ control, name: "kind" });

  function handleKindChange(next: string) {
    // An empty value is the hidden native select re-registering its options, never a choice.
    if (!next) return;
    const changed = withKind(getValues(), next as ReferenceKind);
    setValue("kind", changed.kind);
    setValue("label", changed.label);
  }

  async function onSubmit(values: ReferenceFormValues) {
    setFormError(null);
    const payload = toReferenceInput(values);
    try {
      if (referenceId) {
        await updateProjectReference(projectId, referenceId, payload);
      } else {
        await addProjectReference(projectId, payload);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save reference."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {referenceId ? t("Edit project reference") : t("Add project reference")}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="reference-kind">{t("Type")}</Label>
            <Select value={kind} onValueChange={handleKindChange}>
              <SelectTrigger id="reference-kind" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REFERENCE_KINDS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {t(REFERENCE_KIND_LABELS[option])}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {kind === "custom" && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="reference-label">{t("Label")}</Label>
              <Input
                id="reference-label"
                maxLength={100}
                aria-invalid={!!errors.label}
                {...register("label")}
              />
              {errors.label && (
                <p className="text-destructive text-sm">{errors.label.message}</p>
              )}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Label htmlFor="reference-value">{t("Value")}</Label>
            <Input
              id="reference-value"
              maxLength={255}
              aria-invalid={!!errors.value}
              {...register("value")}
            />
            {errors.value && (
              <p className="text-destructive text-sm">{errors.value.message}</p>
            )}
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
