import type { UseFormReturn } from "react-hook-form";
import { useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { AddressFields } from "@/components/companies/AddressFields";
import type { InvoiceFormValues } from "@/components/invoices/invoiceForm";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addressToFields, type PartySide } from "@/lib/invoiceParties";
import { ADDRESS_TYPE_LABELS } from "@/types/company";
import type { ContextCompany } from "@/types/invoice";

interface PartyFieldsProps {
  side: PartySide;
  title: string;
  /** The company the party was pre-filled from, offering its addresses. */
  company: ContextCompany | null;
  form: UseFormReturn<InvoiceFormValues>;
  disabled?: boolean;
}

/**
 * One billing party: a pre-filled name and address that stay fully editable, with a
 * dropdown of the company's addresses when it has more than one. The dropdown only copies
 * an address into the fields; the invoice keeps what the fields hold.
 */
export function PartyFields({ side, title, company, form, disabled }: PartyFieldsProps) {
  const { t } = useTranslation(["invoices", "company"]);
  const {
    register,
    setValue,
    control,
    formState: { errors },
  } = form;
  const country = useWatch({ control, name: `${side}.address.country_code` });
  const sideErrors = errors[side];
  const addresses = company?.addresses ?? [];

  function pickAddress(id: string) {
    const address = addresses.find((candidate) => candidate.id === id);
    if (!address) return;
    setValue(`${side}.address`, addressToFields(address), {
      shouldDirty: true,
      shouldValidate: true,
    });
  }

  return (
    <fieldset className="flex flex-col gap-4 rounded-md border p-4" disabled={disabled}>
      <legend className="px-1 text-sm font-medium">{title}</legend>
      {addresses.length > 1 && (
        <div className="flex flex-col gap-2">
          <Label htmlFor={`${side}_address_pick`}>{t("Address")}</Label>
          <Select onValueChange={pickAddress} disabled={disabled}>
            <SelectTrigger id={`${side}_address_pick`}>
              <SelectValue placeholder={t("Copy one of the company's addresses…")} />
            </SelectTrigger>
            <SelectContent>
              {addresses.map((address) => (
                <SelectItem key={address.id} value={address.id}>
                  {t(ADDRESS_TYPE_LABELS[address.address_type], { ns: "company" })}
                  {address.is_primary ? ` (${t("Primary", { ns: "company" })})` : ""} —{" "}
                  {address.line1}, {address.city}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="flex flex-col gap-2">
        <Label htmlFor={`${side}_name`}>{t("Name")}</Label>
        <Input
          id={`${side}_name`}
          maxLength={255}
          aria-invalid={!!sideErrors?.name}
          {...register(`${side}.name`)}
        />
        {sideErrors?.name && (
          <p className="text-destructive text-sm">{sideErrors.name.message}</p>
        )}
      </div>
      <AddressFields
        idPrefix={`${side}_`}
        field={(name) => register(`${side}.address.${name}`)}
        country={{
          value: country,
          onChange: (code) =>
            setValue(`${side}.address.country_code`, code, {
              shouldDirty: true,
              shouldValidate: true,
            }),
        }}
        errors={{
          line1: sideErrors?.address?.line1?.message,
          city: sideErrors?.address?.city?.message,
          country_code: sideErrors?.address?.country_code?.message,
        }}
      />
    </fieldset>
  );
}
