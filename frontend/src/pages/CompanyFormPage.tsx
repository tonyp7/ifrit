import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { createCompany, getCompany, updateCompany } from "@/api/companies";
import { AddressesTable } from "@/components/companies/AddressesTable";
import { PartyIdentifiersTable } from "@/components/companies/PartyIdentifiersTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CompanyDetail } from "@/types/company";

const BLANK_VALUES = {
  is_vendor: false,
  legal_name: "",
  trading_name: "",
  legal_form: "",
  country_of_registration: "",
};

export function CompanyFormPage() {
  const { companyId: routeCompanyId } = useParams<{ companyId: string }>();
  const isNew = !routeCompanyId;
  const navigate = useNavigate();
  const { t } = useTranslation(["company", "common"]);

  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Built inside the component (not at module scope) so the validation messages can
  // go through t() — see docs/architecture/frontend.md#internationalization-i18n.
  const schema = useMemo(
    () =>
      z.object({
        is_vendor: z.boolean(),
        legal_name: z.string().min(1, t("Legal name is required")),
        trading_name: z.string().optional(),
        legal_form: z.string().optional(),
        country_of_registration: z
          .string()
          .length(2, t("Must be a 2-letter ISO 3166-1 country code"))
          .transform((v) => v.toUpperCase()),
      }),
    [t],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: BLANK_VALUES });

  const refreshCompany = () => {
    if (!routeCompanyId) return;
    getCompany(routeCompanyId)
      .then((detail) => {
        setCompany(detail);
        reset({
          is_vendor: detail.is_vendor,
          legal_name: detail.legal_name,
          trading_name: detail.trading_name ?? "",
          legal_form: detail.legal_form ?? "",
          country_of_registration: detail.country_of_registration,
        });
      })
      .catch((err: unknown) => {
        setLoadError(err instanceof ApiError ? err.message : t("Failed to load company."));
      });
  };

  useEffect(() => {
    if (routeCompanyId) {
      refreshCompany();
    } else {
      setCompany(null);
      reset(BLANK_VALUES);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeCompanyId]);

  function buildPayload(values: FormValues) {
    return {
      ...values,
      trading_name: values.trading_name || null,
      legal_form: values.legal_form || null,
    };
  }

  async function saveNewCompany(values: FormValues): Promise<CompanyDetail> {
    const created = await createCompany(buildPayload(values));
    setCompany(created);
    navigate(`/configuration/companies/${created.id}`, { replace: true });
    return created;
  }

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      if (company) {
        const updated = await updateCompany(company.id, buildPayload(values));
        setCompany(updated);
      } else {
        await saveNewCompany(values);
      }
      toast.success(t("Company saved."));
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save company."));
    }
  }

  /**
   * Validates and (if needed) saves the company before a Party
   * Identifier/Address can be attached to it — a row can only attach to a
   * persisted company. Returns the company id, or null if validation failed
   * (the form's own error state is already showing why).
   */
  function ensureSaved(): Promise<string | null> {
    if (company) return Promise.resolve(company.id);
    return new Promise((resolve) => {
      void handleSubmit(
        async (values) => {
          setFormError(null);
          try {
            const created = await saveNewCompany(values);
            resolve(created.id);
          } catch (err) {
            setFormError(err instanceof ApiError ? err.message : t("Failed to save company."));
            resolve(null);
          }
        },
        () => resolve(null),
      )();
    });
  }

  if (routeCompanyId && loadError) {
    return <p className="p-4 text-sm text-destructive">{loadError}</p>;
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <Card>
        <CardHeader>
          <CardTitle>{isNew ? t("New Company") : t("Edit Company")}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* One form for the whole card: base fields, then Party Identifiers/Addresses
              (their own dialogs render via a Portal, so nesting them here is safe — no
              actual nested <form> in the DOM), then the Save/Close footer at the very
              bottom, in the conventional position — not sandwiched above the tables. */}
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="is_vendor"
                  checked={watch("is_vendor")}
                  onCheckedChange={(checked) => setValue("is_vendor", checked === true)}
                />
                <Label htmlFor="is_vendor">{t("Vendor")}</Label>
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="legal_name">{t("Legal name")}</Label>
                <Input id="legal_name" {...register("legal_name")} />
                {errors.legal_name && (
                  <p className="text-sm text-destructive">{errors.legal_name.message}</p>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="trading_name">{t("Trading name")}</Label>
                <Input id="trading_name" {...register("trading_name")} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="legal_form">{t("Legal form")}</Label>
                  <Input
                    id="legal_form"
                    placeholder={t("Ltd, GmbH, SA…")}
                    {...register("legal_form")}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="country_of_registration">
                    {t("Country of registration")}
                  </Label>
                  <Input
                    id="country_of_registration"
                    maxLength={2}
                    {...register("country_of_registration")}
                  />
                  {errors.country_of_registration && (
                    <p className="text-sm text-destructive">
                      {errors.country_of_registration.message}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="border-t pt-6">
              <PartyIdentifiersTable
                companyId={company?.id ?? null}
                identifiers={company?.identifiers ?? []}
                onChanged={refreshCompany}
                ensureSaved={ensureSaved}
              />
            </div>

            <div className="border-t pt-6">
              <AddressesTable
                companyId={company?.id ?? null}
                addresses={company?.addresses ?? []}
                onChanged={refreshCompany}
                ensureSaved={ensureSaved}
              />
            </div>

            {formError && <p className="text-sm text-destructive">{formError}</p>}

            <div className="flex justify-between border-t pt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate("/configuration/companies")}
              >
                {t("Close", { ns: "common" })}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {t("Save", { ns: "common" })}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
