import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { listCompanies } from "@/api/companies";
import { listCurrencies } from "@/api/currencies";
import { createProject, getProject, updateProject } from "@/api/projects";
import { ProjectManagersPicker } from "@/components/projects/ProjectManagersPicker";
import { ServiceLinesTable } from "@/components/projects/ServiceLinesTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { formatMoney } from "@/lib/format";
import type { CompanyListItem } from "@/types/company";
import type { Currency } from "@/types/currency";
import {
  PROJECT_TYPE_LABELS,
  STATUS_LABELS,
  type ProjectDetail,
  type ProjectManager,
  type ProjectStatus,
  type ProjectType,
} from "@/types/project";

const PROJECT_TYPE_VALUES = Object.keys(PROJECT_TYPE_LABELS) as [ProjectType, ...ProjectType[]];
const STATUS_VALUES = Object.keys(STATUS_LABELS) as [ProjectStatus, ...ProjectStatus[]];

const BLANK_VALUES = {
  name: "",
  vendor_company_id: "",
  client_company_id: "",
  invoicing_currency: "",
  project_type: "time_and_material" as ProjectType,
  status: "draft" as ProjectStatus,
  project_manager_ids: [] as string[],
};

export function ProjectFormPage() {
  const { projectId: routeProjectId } = useParams<{ projectId: string }>();
  const isNew = !routeProjectId;
  const navigate = useNavigate();
  const { t } = useTranslation(["projects", "common"]);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [vendors, setVendors] = useState<CompanyListItem[]>([]);
  const [clients, setClients] = useState<CompanyListItem[]>([]);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  // Full manager objects, kept alongside the form's own project_manager_ids field —
  // the field is the source of truth for submission, this is only so the picker's
  // chips can render a full_name without an extra fetch (same split as
  // ServiceLineFormDialog's selectedConsultants/user_ids).
  const [selectedManagers, setSelectedManagers] = useState<ProjectManager[]>([]);

  const isReadOnly = project?.status === "closed";

  // Built inside the component (not at module scope) so the validation messages can
  // go through t(), which isn't available at module scope.
  const schema = useMemo(
    () =>
      z.object({
        name: z.string().min(1, t("Name is required")),
        vendor_company_id: z.string().min(1, t("Vendor is required")),
        client_company_id: z.string().min(1, t("Client is required")),
        invoicing_currency: z.string().min(1, t("Currency is required")),
        project_type: z.enum(PROJECT_TYPE_VALUES),
        status: z.enum(STATUS_VALUES),
        project_manager_ids: z.array(z.string()),
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

  useEffect(() => {
    listCompanies({ is_vendor: true })
      .then((r) => setVendors(r.items))
      .catch(() => setVendors([]));
    listCompanies({})
      .then((r) => setClients(r.items))
      .catch(() => setClients([]));
    listCurrencies()
      .then(setCurrencies)
      .catch(() => setCurrencies([]));
  }, []);

  const refreshProject = () => {
    if (!routeProjectId) return;
    getProject(routeProjectId)
      .then((detail) => {
        setProject(detail);
        setSelectedManagers(detail.project_managers);
        reset({
          name: detail.name,
          // Null on a duplicate whose company was soft-deleted: start empty so the
          // "required" validation forces picking a valid one.
          vendor_company_id: detail.vendor_company_id ?? "",
          client_company_id: detail.client_company_id ?? "",
          invoicing_currency: detail.invoicing_currency,
          project_type: detail.project_type,
          status: detail.status,
          project_manager_ids: detail.project_managers.map((m) => m.id),
        });
      })
      .catch((err: unknown) => {
        setLoadError(err instanceof ApiError ? err.message : t("Failed to load project."));
      });
  };

  useEffect(() => {
    if (routeProjectId) {
      refreshProject();
    } else {
      setProject(null);
      setSelectedManagers([]);
      reset(BLANK_VALUES);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeProjectId]);

  async function saveNewProject(values: FormValues): Promise<ProjectDetail> {
    const created = await createProject(values);
    setProject(created);
    navigate(`/projects/${created.id}`, { replace: true });
    return created;
  }

  async function onSubmit(values: FormValues) {
    setFormError(null);
    // The inline "no longer active" message is already showing on the field(s).
    if (
      !isReadOnly &&
      (isInactiveLink("vendor", values.vendor_company_id) ||
        isInactiveLink("client", values.client_company_id))
    ) {
      return;
    }
    try {
      if (project) {
        const updated = await updateProject(project.id, values);
        setProject(updated);
      } else {
        await saveNewProject(values);
      }
      toast.success(t("Project saved."));
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save project."));
    }
  }

  /**
   * Validates and (if needed) saves the project before a Service Line can be attached
   * to it — a row can only attach to a persisted project. Returns the project id, or
   * null if validation failed (the form's own error state is already showing why).
   */
  function ensureSaved(): Promise<string | null> {
    if (project) return Promise.resolve(project.id);
    return new Promise((resolve) => {
      void handleSubmit(
        async (values) => {
          setFormError(null);
          try {
            const created = await saveNewProject(values);
            resolve(created.id);
          } catch (err) {
            setFormError(err instanceof ApiError ? err.message : t("Failed to save project."));
            resolve(null);
          }
        },
        () => resolve(null),
      )();
    });
  }

  /**
   * True while the form still holds the project's original company for `side` and that
   * company has been soft-deleted since — the link is still valid on the project, but
   * saving needs a replacement (the backend rejects an inactive company on write).
   */
  function isInactiveLink(side: "vendor" | "client", selectedId: string): boolean {
    if (!project) return false;
    return (
      project[`${side}_company_is_active`] === false &&
      project[`${side}_company_id`] === selectedId
    );
  }

  /**
   * `onValueChange` for the selects whose options load asynchronously (vendor, client,
   * currency). Radix Select mirrors its value into a hidden native `<select>`; when the
   * options re-register (e.g. the async list arriving after `reset()` already set the
   * value), the native `<select>` briefly has no matching option, snaps to "" and fires a
   * change event — which would otherwise clear the form value we just loaded. These
   * selects have no "clear" option, so an empty value is never a real user choice.
   */
  function handleSelectChange(field: "vendor_company_id" | "client_company_id" | "invoicing_currency") {
    return (value: string) => {
      if (value) setValue(field, value);
    };
  }

  function handleManagersChange(next: ProjectManager[]) {
    setSelectedManagers(next);
    setValue(
      "project_manager_ids",
      next.map((m) => m.id),
    );
  }

  if (routeProjectId && loadError) {
    return <p className="p-4 text-sm text-destructive">{loadError}</p>;
  }

  const vendorId = watch("vendor_company_id");
  const clientId = watch("client_company_id");
  const vendorInactive = !isReadOnly && isInactiveLink("vendor", vendorId);
  const clientInactive = !isReadOnly && isInactiveLink("client", clientId);
  const currencyCode = watch("invoicing_currency");
  const projectType = watch("project_type");
  const status = watch("status");
  // Drives currency-aware decimal formatting for the Service Lines table and Total
  // value below (e.g. 2 decimals for USD, 0 for JPY).
  const selectedCurrency = currencies.find((c) => c.alpha_code === currencyCode);

  return (
    <div className="mx-auto max-w-3xl p-4">
      <Card>
        <CardHeader>
          <CardTitle>{isNew ? t("New Project") : t("Edit Project")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)}>
            <FieldGroup>
              <Field data-invalid={!!errors.name}>
                <FieldLabel htmlFor="name">{t("Name")}</FieldLabel>
                <Input
                  id="name"
                  disabled={isReadOnly}
                  aria-invalid={!!errors.name}
                  {...register("name")}
                />
                <FieldError errors={errors.name && [errors.name]} />
              </Field>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field data-invalid={!!errors.vendor_company_id || vendorInactive}>
                  <FieldLabel htmlFor="vendor_company_id">{t("Vendor")}</FieldLabel>
                  <Select
                    disabled={isReadOnly}
                    value={vendorId}
                    onValueChange={handleSelectChange("vendor_company_id")}
                  >
                    <SelectTrigger id="vendor_company_id" aria-invalid={!!errors.vendor_company_id}>
                      <SelectValue placeholder={t("Select a vendor…")} />
                    </SelectTrigger>
                    <SelectContent>
                      {project?.vendor_company_is_active === false &&
                        project.vendor_company_id && (
                          <SelectItem value={project.vendor_company_id} disabled>
                            {t("{{name}} (inactive)", { name: project.vendor_company_name })}
                          </SelectItem>
                        )}
                      {vendors.map((company) => (
                        <SelectItem key={company.id} value={company.id}>
                          {company.legal_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FieldError
                    errors={
                      errors.vendor_company_id
                        ? [errors.vendor_company_id]
                        : vendorInactive
                          ? [{ message: t("This vendor is no longer active. Select another one.") }]
                          : undefined
                    }
                  />
                </Field>
                <Field data-invalid={!!errors.client_company_id || clientInactive}>
                  <FieldLabel htmlFor="client_company_id">{t("Client")}</FieldLabel>
                  <Select
                    disabled={isReadOnly}
                    value={clientId}
                    onValueChange={handleSelectChange("client_company_id")}
                  >
                    <SelectTrigger id="client_company_id" aria-invalid={!!errors.client_company_id}>
                      <SelectValue placeholder={t("Select a client…")} />
                    </SelectTrigger>
                    <SelectContent>
                      {project?.client_company_is_active === false &&
                        project.client_company_id && (
                          <SelectItem value={project.client_company_id} disabled>
                            {t("{{name}} (inactive)", { name: project.client_company_name })}
                          </SelectItem>
                        )}
                      {clients.map((company) => (
                        <SelectItem key={company.id} value={company.id}>
                          {company.legal_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FieldError
                    errors={
                      errors.client_company_id
                        ? [errors.client_company_id]
                        : clientInactive
                          ? [{ message: t("This client is no longer active. Select another one.") }]
                          : undefined
                    }
                  />
                </Field>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field data-invalid={!!errors.invoicing_currency}>
                  <FieldLabel htmlFor="invoicing_currency">{t("Invoicing currency")}</FieldLabel>
                  <Select
                    disabled={isReadOnly}
                    value={currencyCode}
                    onValueChange={handleSelectChange("invoicing_currency")}
                  >
                    <SelectTrigger
                      id="invoicing_currency"
                      aria-invalid={!!errors.invoicing_currency}
                    >
                      <SelectValue placeholder={t("Select a currency…")} />
                    </SelectTrigger>
                    <SelectContent>
                      {currencies.map((currency) => (
                        <SelectItem key={currency.alpha_code} value={currency.alpha_code}>
                          {t(currency.name)} ({currency.alpha_code})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FieldError
                    errors={errors.invoicing_currency && [errors.invoicing_currency]}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="project_type">{t("Project type")}</FieldLabel>
                  <Select
                    disabled={isReadOnly}
                    value={projectType}
                    onValueChange={(value) => setValue("project_type", value as ProjectType)}
                  >
                    <SelectTrigger id="project_type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PROJECT_TYPE_VALUES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {t(PROJECT_TYPE_LABELS[value])}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field>
                  {/* status stays editable even when the rest of the form is read-only —
                      otherwise a closed project could never be reopened. */}
                  <FieldLabel htmlFor="status">{t("Status")}</FieldLabel>
                  <Select
                    value={status}
                    onValueChange={(value) => setValue("status", value as ProjectStatus)}
                  >
                    <SelectTrigger id="status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_VALUES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {t(STATUS_LABELS[value])}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel>{t("Total value")}</FieldLabel>
                  <p className="flex h-10 items-center text-sm">
                    {project
                      ? `${formatMoney(project.total_value, selectedCurrency?.minor_unit)} ${project.invoicing_currency}`
                      : "—"}
                  </p>
                </Field>
              </div>

              <Separator />

              <Field>
                <FieldLabel>{t("Project Managers")}</FieldLabel>
                <ProjectManagersPicker
                  selected={selectedManagers}
                  onChange={handleManagersChange}
                  disabled={isReadOnly}
                />
              </Field>

              <Separator />

              <ServiceLinesTable
                projectId={project?.id ?? null}
                serviceLines={project?.service_lines ?? []}
                onChanged={refreshProject}
                ensureSaved={ensureSaved}
                readOnly={isReadOnly}
                minorUnit={selectedCurrency?.minor_unit}
              />

              {formError && <p className="text-sm text-destructive">{formError}</p>}

              <Separator />

              <div className="flex justify-between">
                <Button type="button" variant="outline" onClick={() => navigate("/projects")}>
                  {t("Close", { ns: "common" })}
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Spinner />}
                  {isSubmitting ? t("Saving…", { ns: "common" }) : t("Save", { ns: "common" })}
                </Button>
              </div>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
