import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { addPayeeAccount, updatePayeeAccount } from "@/api/companies";
import { listCurrencies } from "@/api/currencies";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import {
  BLANK_PAYEE_ACCOUNT_VALUES,
  compactIban,
  isValidBic,
  isValidIban,
  missingBankAddressFields,
  schemeForPaymentMeans,
  toPayeeAccountInput,
  type PayeeAccountFormValues,
} from "@/lib/payeeAccounts";
import type { Currency } from "@/types/currency";
import {
  ACCOUNT_SCHEME_LABELS,
  PAYMENT_MEANS_LABELS,
  type AccountScheme,
  type PaymentMeansCode,
} from "@/types/company";

const PAYMENT_MEANS = Object.entries(PAYMENT_MEANS_LABELS) as [PaymentMeansCode, string][];
const PAYMENT_MEANS_VALUES = Object.keys(PAYMENT_MEANS_LABELS) as [
  PaymentMeansCode,
  ...PaymentMeansCode[],
];
const SCHEMES = Object.entries(ACCOUNT_SCHEME_LABELS) as [AccountScheme, string][];
const SCHEME_VALUES = Object.keys(ACCOUNT_SCHEME_LABELS) as [
  AccountScheme,
  ...AccountScheme[],
];

const SEPA: PaymentMeansCode = "58";

interface PayeeAccountFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companyId: string;
  /** Present when editing an existing row in place; absent for add/duplicate-as-new. */
  accountId?: string;
  initialValues?: Partial<PayeeAccountFormValues>;
  onSaved: () => void;
}

export function PayeeAccountFormDialog({
  open,
  onOpenChange,
  companyId,
  accountId,
  initialValues,
  onSaved,
}: PayeeAccountFormDialogProps) {
  // `projects` holds the currency names, translated the same way as on the project form.
  const { t } = useTranslation(["company", "common", "projects"]);
  const [formError, setFormError] = useState<string | null>(null);
  const [currencies, setCurrencies] = useState<Currency[]>([]);

  // Built inside the component so the messages can go through t(). The rules mirror the
  // API's, so a mistyped IBAN is caught here with a translated message rather than coming
  // back as a raw validation error.
  const schema = useMemo(() => {
    const text = z.string();
    return z
      .object({
        payment_means_code: z.enum(PAYMENT_MEANS_VALUES),
        account_scheme: z.enum(SCHEME_VALUES),
        account_identifier: z.string().trim().min(1, t("Account identifier is required")),
        account_name: text,
        currency_code: z.string().min(1, t("Currency is required")),
        bic: text.refine((value) => !value.trim() || isValidBic(value), {
          message: t("A BIC is 8 or 11 letters or digits"),
        }),
        bank_name: text,
        bank_address: z.object({
          line1: text,
          line2: text,
          line3: text,
          city: text,
          postal_zone: text,
          country_subdivision: text,
          country_code: text,
        }),
        is_primary: z.boolean(),
      })
      .superRefine((data, ctx) => {
        if (
          data.account_scheme === "iban" &&
          !isValidIban(compactIban(data.account_identifier))
        ) {
          ctx.addIssue({
            code: "custom",
            path: ["account_identifier"],
            message: t("This is not a valid IBAN"),
          });
        }
        const messages = {
          line1: t("Line 1 is required"),
          city: t("City is required"),
          country_code: t("Must be a 2-letter ISO 3166-1 country code"),
        };
        for (const name of missingBankAddressFields(data.bank_address)) {
          ctx.addIssue({
            code: "custom",
            path: ["bank_address", name],
            message: messages[name],
          });
        }
      });
  }, [t]);

  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<PayeeAccountFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...BLANK_PAYEE_ACCOUNT_VALUES, ...initialValues },
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
    if (open) reset({ ...BLANK_PAYEE_ACCOUNT_VALUES, ...initialValues });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    listCurrencies()
      .then(setCurrencies)
      .catch(() => setFormError(t("Failed to load currencies.")));
  }, [open, t]);

  const paymentMeansCode = useWatch({ control, name: "payment_means_code" });
  const accountScheme = useWatch({ control, name: "account_scheme" });
  const currencyCode = useWatch({ control, name: "currency_code" });
  const watchedIsPrimary = useWatch({ control, name: "is_primary" });

  // An account saved in a currency that has since been disabled keeps it: list it so the
  // select still shows what is stored, even though it can't be chosen again.
  const storedCurrencyMissing =
    !!currencyCode &&
    currencies.length > 0 &&
    !currencies.some((currency) => currency.alpha_code === currencyCode);

  function handlePaymentMeansChange(value: string) {
    const code = value as PaymentMeansCode;
    setValue("payment_means_code", code);
    setValue("account_scheme", schemeForPaymentMeans(code, accountScheme));
  }

  async function onSubmit(values: PayeeAccountFormValues) {
    setFormError(null);
    try {
      const payload = toPayeeAccountInput(values);
      if (accountId) {
        await updatePayeeAccount(companyId, accountId, payload);
      } else {
        await addPayeeAccount(companyId, payload);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save payee account."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {accountId ? t("Edit payee account") : t("Add payee account")}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="payment_means_code">{t("Payment means")}</Label>
              <Select value={paymentMeansCode} onValueChange={handlePaymentMeansChange}>
                <SelectTrigger id="payment_means_code">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAYMENT_MEANS.map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {t(label)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="account_scheme">{t("Scheme")}</Label>
              <Select
                value={accountScheme}
                onValueChange={(value) => setValue("account_scheme", value as AccountScheme)}
              >
                <SelectTrigger id="account_scheme">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SCHEMES.map(([value, label]) => (
                    <SelectItem
                      key={value}
                      value={value}
                      disabled={value !== "iban" && paymentMeansCode === SEPA}
                    >
                      {t(label)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="account_identifier">
              {accountScheme === "iban" ? t("IBAN") : t("Account number")}
            </Label>
            <Input
              id="account_identifier"
              aria-invalid={!!errors.account_identifier}
              {...register("account_identifier")}
            />
            {errors.account_identifier && (
              <p className="text-destructive text-sm">{errors.account_identifier.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="account_name">{t("Account name")}</Label>
            <Input id="account_name" {...register("account_name")} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="currency_code">{t("Currency")}</Label>
              <Select
                value={currencyCode}
                // Radix Select clears to "" when its options re-register after the async
                // list arrives; there is no "none" option, so "" is never a real choice.
                onValueChange={(value) => value && setValue("currency_code", value)}
              >
                <SelectTrigger id="currency_code" aria-invalid={!!errors.currency_code}>
                  <SelectValue placeholder={t("Select a currency…")} />
                </SelectTrigger>
                <SelectContent>
                  {storedCurrencyMissing && (
                    <SelectItem value={currencyCode} disabled>
                      {currencyCode}
                    </SelectItem>
                  )}
                  {currencies.map((currency) => (
                    <SelectItem key={currency.alpha_code} value={currency.alpha_code}>
                      {t(currency.name, { ns: "projects" })} ({currency.alpha_code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.currency_code && (
                <p className="text-destructive text-sm">{errors.currency_code.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bic">{t("BIC")}</Label>
              <Input
                id="bic"
                maxLength={11}
                aria-invalid={!!errors.bic}
                {...register("bic")}
              />
              {errors.bic && <p className="text-destructive text-sm">{errors.bic.message}</p>}
            </div>
          </div>

          <Separator />

          <div className="flex flex-col gap-2">
            <Label htmlFor="bank_name">{t("Bank name")}</Label>
            <Input id="bank_name" {...register("bank_name")} />
          </div>

          <p className="text-sm font-medium">{t("Bank address")}</p>
          <AddressFields
            idPrefix="bank_"
            field={(name) => register(`bank_address.${name}`)}
            errors={{
              line1: errors.bank_address?.line1?.message,
              city: errors.bank_address?.city?.message,
              country_code: errors.bank_address?.country_code?.message,
            }}
          />

          <div className="flex items-center gap-2">
            <Checkbox
              id="is_primary"
              checked={watchedIsPrimary}
              onCheckedChange={(checked) => setValue("is_primary", checked === true)}
            />
            <Label htmlFor="is_primary">{t("Primary for this currency")}</Label>
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
