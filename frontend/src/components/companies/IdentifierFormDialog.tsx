import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addIdentifier, updateIdentifier } from "@/api/companies";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { ID_TYPE_LABELS, type IdentifierType } from "@/types/company";

const ID_TYPES = Object.entries(ID_TYPE_LABELS) as [IdentifierType, string][];
const ID_TYPE_VALUES = Object.keys(ID_TYPE_LABELS) as [IdentifierType, ...IdentifierType[]];

const SCHEME_REQUIRED: IdentifierType[] = ["legal_registration", "peppol_participant"];

// Shape-only, used purely for type inference: the validated instance (with
// translated messages) is built inside the component via useMemo below, since
// message strings need t(), which isn't available at module scope.
const _shapeSchema = z.object({
  id_type: z.enum(ID_TYPE_VALUES),
  scheme_id: z.string().optional(),
  id_value: z.string(),
  is_primary: z.boolean(),
});
type FormValues = z.infer<typeof _shapeSchema>;

const BLANK_VALUES: FormValues = {
  id_type: "vat",
  scheme_id: "",
  id_value: "",
  is_primary: false,
};

interface IdentifierFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  /** Present when editing an existing row in place; absent for add/duplicate-as-new. */
  identifierId?: string;
  initialValues?: Partial<FormValues>;
  onSaved: () => void;
}

export function IdentifierFormDialog({
  open,
  onOpenChange,
  companyId,
  identifierId,
  initialValues,
  onSaved,
}: IdentifierFormDialogProps) {
  const { t } = useTranslation(["company", "common"]);
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(
    () =>
      z
        .object({
          id_type: z.enum(ID_TYPE_VALUES),
          scheme_id: z.string().optional(),
          id_value: z.string().min(1, t("Value is required")),
          is_primary: z.boolean(),
        })
        .refine((data) => !SCHEME_REQUIRED.includes(data.id_type) || !!data.scheme_id?.trim(), {
          message: t("Scheme ID is required for this identifier type"),
          path: ["scheme_id"],
        }),
    [t],
  );

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...BLANK_VALUES, ...initialValues },
  });

  useEffect(() => {
    if (open) {
      setFormError(null);
      reset({ ...BLANK_VALUES, ...initialValues });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const idType = watch("id_type");

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      const payload = { ...values, scheme_id: values.scheme_id || null };
      if (identifierId) {
        await updateIdentifier(companyId, identifierId, payload);
      } else {
        await addIdentifier(companyId, payload);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save identifier."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{identifierId ? t("Edit identifier") : t("Add identifier")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="id_type">{t("Type")}</Label>
            <Select
              value={idType}
              onValueChange={(value) => setValue("id_type", value as IdentifierType)}
            >
              <SelectTrigger id="id_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ID_TYPES.map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {t(label)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="scheme_id">
              {SCHEME_REQUIRED.includes(idType)
                ? t("Scheme ID (required)")
                : t("Scheme ID (optional)")}
            </Label>
            <Input id="scheme_id" {...register("scheme_id")} />
            {errors.scheme_id && (
              <p className="text-sm text-destructive">{errors.scheme_id.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="id_value">{t("Value")}</Label>
            <Input id="id_value" {...register("id_value")} />
            {errors.id_value && (
              <p className="text-sm text-destructive">{errors.id_value.message}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="is_primary"
              checked={watch("is_primary")}
              onCheckedChange={(checked) => setValue("is_primary", checked === true)}
            />
            <Label htmlFor="is_primary">{t("Primary")}</Label>
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
