import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addAddress, updateAddress } from "@/api/companies";
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
import { ADDRESS_TYPE_LABELS, type AddressType } from "@/types/company";

const ADDRESS_TYPES = Object.entries(ADDRESS_TYPE_LABELS) as [AddressType, string][];
const ADDRESS_TYPE_VALUES = Object.keys(ADDRESS_TYPE_LABELS) as [AddressType, ...AddressType[]];

// Shape-only, used purely for type inference — the validated instance (with
// translated messages) is built inside the component via useMemo below, since
// message strings need t() (see docs/architecture/frontend.md#internationalization-i18n).
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

  const addressType = watch("address_type");

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

          <div className="flex flex-col gap-2">
            <Label htmlFor="line1">{t("Line 1")}</Label>
            <Input id="line1" {...register("line1")} />
            {errors.line1 && <p className="text-sm text-destructive">{errors.line1.message}</p>}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="line2">{t("Line 2")}</Label>
            <Input id="line2" {...register("line2")} />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="line3">{t("Line 3")}</Label>
            <Input id="line3" {...register("line3")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="city">{t("City")}</Label>
              <Input id="city" {...register("city")} />
              {errors.city && <p className="text-sm text-destructive">{errors.city.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="postal_zone">{t("Postal code")}</Label>
              <Input id="postal_zone" {...register("postal_zone")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="country_subdivision">{t("State / province")}</Label>
              <Input id="country_subdivision" {...register("country_subdivision")} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="country_code">{t("Country code")}</Label>
              <Input id="country_code" maxLength={2} {...register("country_code")} />
              {errors.country_code && (
                <p className="text-sm text-destructive">{errors.country_code.message}</p>
              )}
            </div>
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
