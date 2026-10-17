import { useEffect, useState } from "react";
import type { UseFormReturn } from "react-hook-form";
import { useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { listCurrencies } from "@/api/currencies";
import { AddressFields } from "@/components/companies/AddressFields";
import type { InvoiceFormValues } from "@/components/invoices/invoiceForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { orderPayeeAccounts, payeeFormFromAccount } from "@/lib/invoicePayee";
import {
  BLANK_PAYEE_ACCOUNT_VALUES,
  formatAccountIdentifier,
  schemeForPaymentMeans,
} from "@/lib/payeeAccounts";
import {
  ACCOUNT_SCHEME_LABELS,
  PAYMENT_MEANS_LABELS,
  type AccountScheme,
  type PaymentMeansCode,
} from "@/types/company";
import type { Currency } from "@/types/currency";
import type { ContextPayeeAccount } from "@/types/invoice";

const PAYMENT_MEANS = Object.entries(PAYMENT_MEANS_LABELS) as [PaymentMeansCode, string][];
const SCHEMES = Object.entries(ACCOUNT_SCHEME_LABELS) as [AccountScheme, string][];

interface PayeeAccountFieldsProps {
  accounts: ContextPayeeAccount[];
  invoiceCurrency: string | null;
  form: UseFormReturn<InvoiceFormValues>;
  disabled?: boolean;
}

/**
 * The account the invoice asks to be paid into. Picking one of the vendor's accounts copies
 * its details into the fields, which stay editable and are saved on the invoice as they are:
 * nothing links back to the account, so later changes to it never reach the invoice. The
 * inputs and their rules are those of the company payee account dialog.
 */
export function PayeeAccountFields({
  accounts,
  invoiceCurrency,
  form,
  disabled,
}: PayeeAccountFieldsProps) {
  const { t } = useTranslation(["invoices", "company", "projects"]);
  const {
    register,
    setValue,
    control,
    formState: { errors },
  } = form;
  const payee = useWatch({ control, name: "payee" });
  const [currencies, setCurrencies] = useState<Currency[]>([]);

  useEffect(() => {
    listCurrencies()
      .then(setCurrencies)
      .catch(() => setCurrencies([]));
  }, []);

  const set = { shouldDirty: true, shouldValidate: true } as const;
  const payeeErrors = errors.payee;
  const ordered = orderPayeeAccounts(accounts, invoiceCurrency ?? "");
  // A copied currency may since have been disabled: keep it listed so the select still
  // shows what the invoice holds.
  const currencyMissing =
    !!payee?.currency_code && !currencies.some((c) => c.alpha_code === payee.currency_code);

  function pick(id: string) {
    const account = accounts.find((candidate) => candidate.id === id);
    if (account) setValue("payee", payeeFormFromAccount(account), set);
  }

  return (
    <fieldset className="flex flex-col gap-4 rounded-md border p-4" disabled={disabled}>
      <legend className="px-1 text-sm font-medium">{t("Payee account")}</legend>
      <div className="flex flex-col gap-2">
        <Label htmlFor="payee_pick">{t("Copy from the vendor's accounts")}</Label>
        <Select onValueChange={pick} disabled={disabled || accounts.length === 0}>
          <SelectTrigger id="payee_pick">
            <SelectValue
              placeholder={
                accounts.length
                  ? t("Choose an account…")
                  : t("The vendor has no payee account")
              }
            />
          </SelectTrigger>
          <SelectContent>
            {ordered.map((account) => (
              <SelectItem key={account.id} value={account.id}>
                {formatAccountIdentifier(account.account_scheme, account.account_identifier)} (
                {account.currency_code}
                {account.is_primary ? `, ${t("primary")}` : ""})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {payee === null ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-muted-foreground text-sm">
            {t("No payee account on this invoice.")}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() =>
              setValue(
                "payee",
                { ...BLANK_PAYEE_ACCOUNT_VALUES, currency_code: invoiceCurrency ?? "" },
                set,
              )
            }
          >
            {t("Enter account details")}
          </Button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="payee_payment_means_code">
                {t("Payment means", { ns: "company" })}
              </Label>
              <Select
                value={payee.payment_means_code}
                disabled={disabled}
                onValueChange={(value) => {
                  const code = value as PaymentMeansCode;
                  setValue("payee.payment_means_code", code, set);
                  setValue(
                    "payee.account_scheme",
                    schemeForPaymentMeans(code, payee.account_scheme),
                    set,
                  );
                }}
              >
                <SelectTrigger id="payee_payment_means_code">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAYMENT_MEANS.map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {t(label, { ns: "company" })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="payee_account_scheme">{t("Scheme", { ns: "company" })}</Label>
              <Select
                value={payee.account_scheme}
                disabled={disabled}
                onValueChange={(value) =>
                  setValue("payee.account_scheme", value as AccountScheme, set)
                }
              >
                <SelectTrigger id="payee_account_scheme">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SCHEMES.map(([value, label]) => (
                    <SelectItem
                      key={value}
                      value={value}
                      disabled={value !== "iban" && payee.payment_means_code === "58"}
                    >
                      {t(label, { ns: "company" })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="payee_account_identifier">
                {payee.account_scheme === "iban"
                  ? t("IBAN", { ns: "company" })
                  : t("Account number", { ns: "company" })}
              </Label>
              <Input
                id="payee_account_identifier"
                aria-invalid={!!payeeErrors?.account_identifier}
                {...register("payee.account_identifier")}
              />
              {payeeErrors?.account_identifier && (
                <p className="text-destructive text-sm">
                  {payeeErrors.account_identifier.message}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="payee_account_name">
                {t("Account name", { ns: "company" })}
              </Label>
              <Input id="payee_account_name" {...register("payee.account_name")} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="payee_currency_code">{t("Currency", { ns: "company" })}</Label>
              <Select
                value={payee.currency_code}
                disabled={disabled}
                onValueChange={(value) => value && setValue("payee.currency_code", value, set)}
              >
                <SelectTrigger
                  id="payee_currency_code"
                  aria-invalid={!!payeeErrors?.currency_code}
                >
                  <SelectValue placeholder={t("Select a currency…", { ns: "company" })} />
                </SelectTrigger>
                <SelectContent>
                  {currencyMissing && (
                    <SelectItem value={payee.currency_code}>{payee.currency_code}</SelectItem>
                  )}
                  {currencies.map((currency) => (
                    <SelectItem key={currency.alpha_code} value={currency.alpha_code}>
                      {t(currency.name, { ns: "projects" })} ({currency.alpha_code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {payeeErrors?.currency_code && (
                <p className="text-destructive text-sm">{payeeErrors.currency_code.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="payee_bic">{t("BIC", { ns: "company" })}</Label>
              <Input
                id="payee_bic"
                maxLength={11}
                aria-invalid={!!payeeErrors?.bic}
                {...register("payee.bic")}
              />
              {payeeErrors?.bic && (
                <p className="text-destructive text-sm">{payeeErrors.bic.message}</p>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="payee_bank_name">{t("Bank name", { ns: "company" })}</Label>
            <Input id="payee_bank_name" {...register("payee.bank_name")} />
          </div>
          <p className="text-sm font-medium">{t("Bank address", { ns: "company" })}</p>
          <AddressFields
            idPrefix="payee_bank_"
            field={(name) => register(`payee.bank_address.${name}`)}
            country={{
              value: payee.bank_address.country_code,
              onChange: (code) => setValue("payee.bank_address.country_code", code, set),
            }}
            errors={{
              line1: payeeErrors?.bank_address?.line1?.message,
              city: payeeErrors?.bank_address?.city?.message,
              country_code: payeeErrors?.bank_address?.country_code?.message,
            }}
          />
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={disabled}
              onClick={() => setValue("payee", null, set)}
            >
              {t("Clear payee account")}
            </Button>
          </div>
        </>
      )}
    </fieldset>
  );
}
