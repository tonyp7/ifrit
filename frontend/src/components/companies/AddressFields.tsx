import type { UseFormRegisterReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { CountryPicker } from "@/components/CountryPicker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { AddressFieldName } from "@/lib/payeeAccounts";

interface AddressFieldsProps {
  /** Registers one text field with the parent form, under whatever path the parent keeps it. */
  field: (name: Exclude<AddressFieldName, "country_code">) => UseFormRegisterReturn;
  /** The country is a picker, not a text input, so the parent passes its value and setter. */
  country: { value: string; onChange: (code: string) => void };
  errors: Partial<Record<AddressFieldName, string | undefined>>;
  /** Prepended to every input id, so two address blocks can share a page. */
  idPrefix?: string;
}

/**
 * The postal lines of an address: lines 1–3, city, postal code, state / province and
 * country code. Shared by every dialog that edits an address so their fields, labels and
 * layout cannot drift apart; the address type and primary flag stay with each dialog.
 */
export function AddressFields({ field, country, errors, idPrefix = "" }: AddressFieldsProps) {
  const { t } = useTranslation(["company", "common"]);
  const id = (name: AddressFieldName) => `${idPrefix}${name}`;

  return (
    <>
      <div className="flex flex-col gap-2">
        <Label htmlFor={id("line1")}>{t("Line 1")}</Label>
        <Input id={id("line1")} aria-invalid={!!errors.line1} {...field("line1")} />
        {errors.line1 && <p className="text-destructive text-sm">{errors.line1}</p>}
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={id("line2")}>{t("Line 2")}</Label>
        <Input id={id("line2")} {...field("line2")} />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={id("line3")}>{t("Line 3")}</Label>
        <Input id={id("line3")} {...field("line3")} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor={id("city")}>{t("City")}</Label>
          <Input id={id("city")} aria-invalid={!!errors.city} {...field("city")} />
          {errors.city && <p className="text-destructive text-sm">{errors.city}</p>}
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor={id("postal_zone")}>{t("Postal code")}</Label>
          <Input id={id("postal_zone")} {...field("postal_zone")} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor={id("country_subdivision")}>{t("State / province")}</Label>
          <Input id={id("country_subdivision")} {...field("country_subdivision")} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor={id("country_code")}>{t("Country")}</Label>
          <CountryPicker
            id={id("country_code")}
            value={country.value}
            onChange={country.onChange}
            invalid={!!errors.country_code}
          />
          {errors.country_code && (
            <p className="text-destructive text-sm">{errors.country_code}</p>
          )}
        </div>
      </div>
    </>
  );
}
