import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addAddress, updateAddress } from "@/api/companies";
import { AddressFields } from "@/components/companies/AddressFields";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { ADDRESS_TYPE_LABELS, type AddressType } from "@/types/company";

const ADDRESS_TYPES = Object.entries(ADDRESS_TYPE_LABELS) as [AddressType, string][];
const ADDRESS_TYPE_VALUES = Object.keys(ADDRESS_TYPE_LABELS) as [AddressType, ...AddressType[]];

// Shape-only, used purely for type inference: the validated instance (with
// translated messages) is built inside the component via useMemo below, since
// message strings need t(), which isn't available at module scope.
const _shapeSchema = z.object({
  address_type: z.enum(ADDRESS_TYPE_VALUES),
  line1: z.string(),
  line2: z.string().optional(),
  line3: z.string().optional(),
  city: z.string(),
  postal_zone: z.string().optional(),
  country_subdivision: z.string().optional(),
  country_code: z.string(),
  is_primary: z.boolean(),
});
type FormValues = z.infer<typeof _shapeSchema>;

const BLANK_VALUES: FormValues = {
  address_type: "registered",
  line1: "",
  line2: "",
  line3: "",
  city: "",
  postal_zone: "",
  country_subdivision: "",
  country_code: "",
  is_primary: false,
};

interface AddressFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  /** Present when editing an existing row in place; absent for add/duplicate-as-new. */
  addressId?: string;
  initialValues?: Partial<FormValues>;
  onSaved: () => void;
}

export function AddressFormDialog({
  open,
  onOpenChange,
  companyId,
  addressId,
  initialValues,
  onSaved,
}: AddressFormDialogProps) {
  const { t } = useTranslation(["company", "common"]);
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        address_type: z.enum(ADDRESS_TYPE_VALUES),
        line1: z.string().min(1, t("Line 1 is required")),
        line2: z.string().optional(),
        line3: z.string().optional(),
        city: z.string().min(1, t("City is required")),
        postal_zone: z.string().optional(),
        country_subdivision: z.string().optional(),
        country_code: z
          .string()
          .length(2, t("Must be a 2-letter ISO 3166-1 country code"))
          .transform((v) => v.toUpperCase()),
        is_primary: z.boolean(),
      }),
    [t],
  );

  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...BLANK_VALUES, ...initialValues },
  });

  // Each time the dialog opens it starts from a clean slate. The error message is state of this
  // component, so it is cleared while rendering, by comparing with the previous `open`; the form
  // library's own state is reset in an effect.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setFormError(null);
  }

  useEffect(() => {
    if (open) reset({ ...BLANK_VALUES, ...initialValues });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const addressType = useWatch({ control, name: "address_type" });
  const watchedIsPrimary = useWatch({ control, name: "is_primary" });
  const countryCode = useWatch({ control, name: "country_code" });

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      const payload = {
        ...values,
        line2: values.line2 || null,
        line3: values.line3 || null,
        postal_zone: values.postal_zone || null,
        country_subdivision: values.country_subdivision || null,
      };
      if (addressId) {
        await updateAddress(companyId, addressId, payload);
      } else {
        await addAddress(companyId, payload);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save address."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{addressId ? t("Edit address") : t("Add address")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="address_type">{t("Type")}</Label>
            <Select
              value={addressType}
              onValueChange={(value) => setValue("address_type", value as AddressType)}
            >
              <SelectTrigger id="address_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ADDRESS_TYPES.map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {t(label)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <AddressFields
            field={(name) => register(name)}
            country={{
              value: countryCode,
              onChange: (code) =>
                setValue("country_code", code, { shouldDirty: true, shouldValidate: true }),
            }}
            errors={{
              line1: errors.line1?.message,
              city: errors.city?.message,
              country_code: errors.country_code?.message,
            }}
          />

          <div className="flex items-center gap-2">
            <Checkbox
              id="is_primary"
              checked={watchedIsPrimary}
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
