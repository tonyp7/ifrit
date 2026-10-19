import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  createInvoice,
  deleteInvoice,
  duplicateInvoice,
  generateLines,
  getBillingContext,
  getInvoice,
  getIssuePreview,
  issueInvoice,
  listInvoiceProjects,
  updateInvoice,
  voidInvoice,
} from "@/api/invoices";
import { InvoiceLinesTable } from "@/components/invoices/InvoiceLinesTable";
import { InvoiceTaxesTable } from "@/components/invoices/InvoiceTaxesTable";
import { IssueInvoiceDialog } from "@/components/invoices/IssueInvoiceDialog";
import {
  InvoiceHeading,
  IssuedIdentifiers,
  ProjectNotActiveBanner,
  VoidNotice,
} from "@/components/invoices/IssuedInvoiceDetails";
import { VoidInvoiceDialog } from "@/components/invoices/VoidInvoiceDialog";
import { GenerateLinesGroup } from "@/components/invoices/GenerateLinesGroup";
import { InvoiceReferencesFields } from "@/components/invoices/InvoiceReferencesFields";
import { InvoiceWarnings } from "@/components/invoices/InvoiceWarnings";
import {
  appendGeneratedLines,
  BLANK_INVOICE_FORM,
  fromInvoiceDetail,
  invoiceSchema,
  toInvoiceInput,
  type InvoiceFormValues,
} from "@/components/invoices/invoiceForm";
import { PartyFields } from "@/components/invoices/PartyFields";
import { PaymentSection } from "@/components/invoices/PaymentSection";
import { MilestoneBillingPanel } from "@/components/invoices/MilestoneBillingPanel";
import { TmBillingPanel } from "@/components/invoices/TmBillingPanel";
import { useServiceLineLabel } from "@/hooks/useServiceLineLabel";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
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
import { partyFromCompany } from "@/lib/invoiceParties";
import { payeeFormFromAccount, preselectPayee } from "@/lib/invoicePayee";
import { formatPeriod, isValidPeriod, presetRange } from "@/lib/invoicePeriods";
import { prefillReferences } from "@/lib/invoiceReferences";
import { subtotal } from "@/lib/invoiceMath";
import { computeTaxes } from "@/lib/invoiceTaxes";
import { combineWarnings, formWarnings } from "@/lib/invoiceWarnings";
import { parseDayKey, toDayKey } from "@/lib/timesheetDates";
import {
  type BillingContext,
  type GenerateInput,
  type InvoiceDetail,
  type InvoiceableProject,
  type InvoiceStatus,
  type InvoiceWarning,
  type IssuePreview,
  type OmittedServiceLine,
} from "@/types/invoice";
import { PROJECT_TYPE_LABELS } from "@/types/project";

function newInvoiceValues(today: Date): InvoiceFormValues {
  // Last month is the usual case: invoicing the month that just ended.
  const range = presetRange("last_month", today);
  return {
    ...BLANK_INVOICE_FORM,
    period_preset: "last_month",
    period_start: toDayKey(range.start),
    period_end: toDayKey(range.end),
  };
}

/** The fields a project fills in when it is chosen: parties, payee, references and the
 * service lines to bill, all from the billing context. */
function prefillFromProject(context: BillingContext): Partial<InvoiceFormValues> {
  const account = preselectPayee(context.payee_accounts, context.currency_code);
  return {
    project_id: context.id,
    bill_from: partyFromCompany(context.vendor, "bill_from"),
    bill_to: partyFromCompany(context.client, "bill_to"),
    payee: account ? payeeFormFromAccount(account) : null,
    references: prefillReferences(context.references),
    service_line_ids: context.service_lines.map((line) => line.id),
    lines: [],
  };
}

function SectionHeading({ step, title }: { step: number; title: string }) {
  return (
    <h2 className="flex items-center gap-2 text-sm font-semibold tracking-wide uppercase">
      <span className="bg-secondary flex h-6 w-6 items-center justify-center rounded-full text-xs">
        {step}
      </span>
      {title}
    </h2>
  );
}

export function InvoiceFormPage() {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation(["invoices", "common", "projects"]);
  const [today] = useState(() => new Date());
  const schema = useMemo(() => invoiceSchema(t), [t]);

  const form = useForm<InvoiceFormValues>({
    resolver: zodResolver(schema),
    defaultValues: newInvoiceValues(today),
  });
  const { control, handleSubmit, reset, setValue, getValues } = form;

  const [projects, setProjects] = useState<InvoiceableProject[]>([]);
  const [context, setContext] = useState<BillingContext | null>(null);
  const [status, setStatus] = useState<InvoiceStatus>("draft");
  const [savedProjectName, setSavedProjectName] = useState<string | null>(null);
  const [serverWarnings, setServerWarnings] = useState<InvoiceWarning[]>([]);
  const [omitted, setOmitted] = useState<OmittedServiceLine[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingProject, setPendingProject] = useState<string | null>(null);
  // Fixed Price only: the milestones to generate from. Never ticked for the user.
  const [milestoneIds, setMilestoneIds] = useState<string[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState<
    "saving" | "generating" | "deleting" | "issuing" | "voiding" | "duplicating" | null
  >(null);
  // The saved invoice as the server returned it: the number, dates and snapshot.
  const [detail, setDetail] = useState<InvoiceDetail | null>(null);
  // For a saved draft: the likely number, and what would stop it being issued.
  const [preview, setPreview] = useState<IssuePreview | null>(null);
  const [issueOpen, setIssueOpen] = useState(false);
  const [voidOpen, setVoidOpen] = useState(false);
  // Bumped to read the invoice again after it is saved, issued or voided.
  const [reloadToken, setReloadToken] = useState(0);

  const projectId = useWatch({ control, name: "project_id" });
  const lines = useWatch({ control, name: "lines" });
  const taxes = useWatch({ control, name: "taxes" });
  const payee = useWatch({ control, name: "payee" });
  const serviceLineIds = useWatch({ control, name: "service_line_ids" });
  const periodPreset = useWatch({ control, name: "period_preset" });
  const periodStart = useWatch({ control, name: "period_start" });
  const periodEnd = useWatch({ control, name: "period_end" });
  const paymentTerms = useWatch({ control, name: "payment_terms" });
  const dueDate = useWatch({ control, name: "due_date" });

  const lineLabel = useServiceLineLabel(context?.currency_minor_unit ?? null);
  const readOnly = status !== "draft";

  useEffect(() => {
    listInvoiceProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);

  // A saved draft: its values, then the project's billing context for the pickers.
  useEffect(() => {
    if (!invoiceId) return;
    let cancelled = false;
    getInvoice(invoiceId)
      .then(async (detail) => {
        const projectContext = await getBillingContext(detail.project_id).catch(() => null);
        if (cancelled) return;
        reset({
          ...fromInvoiceDetail(detail),
          service_line_ids: projectContext?.service_lines.map((line) => line.id) ?? [],
        });
        setContext(projectContext);
        setStatus(detail.status);
        setDetail(detail);
        setSavedProjectName(detail.project_name);
        setServerWarnings(detail.warnings);
        setOmitted([]);
        setMilestoneIds([]);
        setLoadError(null);
        if (detail.status === "draft") {
          const loaded = await getIssuePreview(detail.id).catch(() => null);
          if (!cancelled) setPreview(loaded);
        } else {
          setPreview(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError ? err.message : t("Failed to load the invoice."),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [invoiceId, reloadToken, reset, t]);

  // Issue on a new invoice saves it first, which moves to its own address; the
  // confirmation opens once there.
  const openIssueAfterSave = (location.state as { issue?: boolean } | null)?.issue === true;
  useEffect(() => {
    if (!openIssueAfterSave || !invoiceId) return;
    navigate(location.pathname, { replace: true, state: null });
    void openIssueDialog(invoiceId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openIssueAfterSave, invoiceId]);

  async function applyProject(id: string) {
    setFormError(null);
    try {
      const projectContext = await getBillingContext(id);
      for (const [key, value] of Object.entries(prefillFromProject(projectContext))) {
        setValue(key as keyof InvoiceFormValues, value as never, { shouldDirty: true });
      }
      setContext(projectContext);
      setServerWarnings([]);
      setOmitted([]);
      setMilestoneIds([]);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to load the project."));
    }
  }

  // Changing the project replaces the lines, so it asks first when there are some.
  function handleProjectChange(id: string) {
    if (id === projectId) return;
    if (getValues("lines").length > 0) setPendingProject(id);
    else void applyProject(id);
  }

  async function runGenerate() {
    const values = getValues();
    const byMilestone = context?.project_type === "fixed_price";
    let input: GenerateInput;
    if (byMilestone && milestoneIds.length > 0) {
      input = {
        kind: "milestone",
        project_id: values.project_id,
        milestone_ids: milestoneIds,
      };
    } else if (!byMilestone && values.period_start && values.period_end) {
      input = {
        kind: "time",
        project_id: values.project_id,
        service_line_ids: values.service_line_ids,
        period_start: values.period_start,
        period_end: values.period_end,
      };
    } else {
      return;
    }
    setBusy("generating");
    setFormError(null);
    try {
      const result = await generateLines(input);
      const period =
        values.period_start && values.period_end
          ? formatPeriod(parseDayKey(values.period_start), parseDayKey(values.period_end))
          : "";
      setValue(
        "lines",
        appendGeneratedLines(getValues("lines"), result.lines, (line) =>
          // A milestone's description is the line as the contract names it, kept as is.
          byMilestone
            ? (line.name ?? "")
            : t("{{name}} — {{period}}", { name: lineLabel(line), period }),
        ),
        { shouldDirty: true },
      );
      setOmitted(result.omitted);
      setServerWarnings(result.warnings);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to generate the lines."));
    } finally {
      setBusy(null);
    }
  }

  /** Saves the draft; null when it could not be saved (the error is shown). */
  async function save(
    values: InvoiceFormValues,
    issueNext = false,
  ): Promise<InvoiceDetail | null> {
    setBusy("saving");
    setFormError(null);
    try {
      const payload = toInvoiceInput(values);
      const saved = invoiceId
        ? await updateInvoice(invoiceId, payload)
        : await createInvoice(payload);
      toast.success(t("Draft saved"));
      setServerWarnings(saved.warnings);
      if (!invoiceId) {
        navigate(`/invoices/${saved.id}`, {
          replace: true,
          state: issueNext ? { issue: true } : null,
        });
      } else {
        setReloadToken((n) => n + 1);
      }
      return saved;
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save the draft."));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function onSubmit(values: InvoiceFormValues) {
    await save(values);
  }

  async function openIssueDialog(id: string) {
    setPreview(null);
    setIssueOpen(true);
    try {
      setPreview(await getIssuePreview(id));
    } catch (err) {
      setIssueOpen(false);
      setFormError(
        err instanceof ApiError
          ? err.message
          : t("Failed to prepare the invoice for issuing."),
      );
    }
  }

  // Unsaved edits are saved first, so what is issued is what the form shows.
  const handleIssue = handleSubmit(async (values) => {
    if (invoiceId && !form.formState.isDirty) {
      await openIssueDialog(invoiceId);
      return;
    }
    const saved = await save(values, true);
    if (saved && invoiceId) await openIssueDialog(saved.id);
  });

  async function confirmIssue() {
    if (!invoiceId) return;
    setBusy("issuing");
    try {
      const issued = await issueInvoice(invoiceId);
      toast.success(t("Invoice {{number}} issued", { number: issued.number }));
      setIssueOpen(false);
      setReloadToken((n) => n + 1);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to issue the invoice."));
      setIssueOpen(false);
      setReloadToken((n) => n + 1);
    } finally {
      setBusy(null);
    }
  }

  async function confirmVoid(reason: string) {
    if (!invoiceId) return;
    setBusy("voiding");
    try {
      const voided = await voidInvoice(invoiceId, reason);
      toast.success(t("Invoice {{number}} voided", { number: voided.number }));
      setVoidOpen(false);
      setReloadToken((n) => n + 1);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to void the invoice."));
    } finally {
      setBusy(null);
    }
  }

  async function handleDuplicate() {
    if (!invoiceId) return;
    setBusy("duplicating");
    try {
      const copy = await duplicateInvoice(invoiceId);
      toast.success(t("Invoice duplicated"));
      navigate(`/invoices/${copy.id}`);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : t("Failed to duplicate the invoice."),
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete() {
    if (!invoiceId) return;
    setBusy("deleting");
    try {
      await deleteInvoice(invoiceId);
      toast.success(t("Draft deleted"));
      navigate("/invoices");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to delete the draft."));
      setBusy(null);
      setConfirmDelete(false);
    }
  }

  const inactiveFromContext: InvoiceWarning[] = (() => {
    const companies: ("vendor" | "client")[] = [];
    if (context?.vendor && !context.vendor.is_active) companies.push("vendor");
    if (context?.client && !context.client.is_active) companies.push("client");
    return companies.length
      ? [{ code: "inactive_company", service_lines: [], companies }]
      : [];
  })();
  const liveSubtotal = subtotal(lines, context?.currency_minor_unit ?? null);
  const warnings = combineWarnings(
    formWarnings({
      quantities: lines.map((line) => line.quantity),
      payeeCurrency: payee ? payee.currency_code || null : null,
      invoiceCurrency: context?.currency_code ?? null,
      subtotal: liveSubtotal,
      taxes: computeTaxes(liveSubtotal, taxes, context?.currency_minor_unit ?? null).map(
        (tax, index) => ({ ...tax, amount_set_by_hand: taxes[index].amount_set_by_hand }),
      ),
    }),
    [
      ...serverWarnings.filter((warning) => warning.code !== "inactive_company"),
      ...inactiveFromContext,
    ],
  );

  // A saved draft's project may since have left the picker (closed, deleted): keep it
  // listed so the picker still shows what the draft belongs to.
  const projectOptions =
    projectId && !projects.some((project) => project.id === projectId)
      ? [{ id: projectId, name: context?.name ?? savedProjectName ?? "" }, ...projects]
      : projects;
  const isFixedPrice = context?.project_type === "fixed_price";
  const periodValid =
    !!periodStart &&
    !!periodEnd &&
    isValidPeriod({ start: parseDayKey(periodStart), end: parseDayKey(periodEnd) });
  const canGenerate =
    !!context &&
    !readOnly &&
    (isFixedPrice ? milestoneIds.length > 0 : serviceLineIds.length > 0 && periodValid);

  if (loadError) {
    return (
      <div className="p-4">
        <p className="text-destructive text-sm">{loadError}</p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4"
      noValidate
    >
      <div className="flex flex-col gap-2">
        <Link
          to="/invoices"
          className="text-muted-foreground flex items-center gap-1 text-sm hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {t("Invoices")}
        </Link>
        <InvoiceHeading status={status} detail={detail} preview={preview} isNew={!invoiceId} />
      </div>

      {!readOnly && preview && <ProjectNotActiveBanner preview={preview} />}
      {status === "void" && detail && <VoidNotice detail={detail} />}

      <section className="flex flex-col gap-4">
        <SectionHeading step={1} title={t("Project")} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="project_id">{t("Project")}</Label>
            <Select
              value={projectId || undefined}
              onValueChange={handleProjectChange}
              disabled={readOnly}
            >
              <SelectTrigger id="project_id" aria-invalid={!!form.formState.errors.project_id}>
                <SelectValue placeholder={t("Choose a project…")} />
              </SelectTrigger>
              <SelectContent>
                {projectOptions.map((project) => (
                  <SelectItem key={project.id} value={project.id}>
                    {project.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.formState.errors.project_id && (
              <p className="text-destructive text-sm">
                {form.formState.errors.project_id.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">{t("Currency")}</span>
            <p className="text-sm" data-testid="currency">
              {context ? context.currency_code : "—"}
            </p>
            {context && (
              <p className="text-muted-foreground text-sm">
                {t("Type: {{type}}", {
                  type: t(PROJECT_TYPE_LABELS[context.project_type], { ns: "projects" }),
                })}
              </p>
            )}
          </div>
        </div>
      </section>

      {projectId && (
        <>
          <Separator />
          <section className="flex flex-col gap-4">
            <SectionHeading step={2} title={t("References")} />
            <InvoiceReferencesFields form={form} disabled={readOnly} />
          </section>

          <Separator />
          <section className="flex flex-col gap-4">
            <SectionHeading step={3} title={t("Parties")} />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <PartyFields
                side="bill_from"
                title={t("Bill From")}
                company={context?.vendor ?? null}
                form={form}
                disabled={readOnly}
              />
              <PartyFields
                side="bill_to"
                title={t("Bill To")}
                company={context?.client ?? null}
                form={form}
                disabled={readOnly}
              />
            </div>
            {readOnly && detail && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <IssuedIdentifiers
                  title={t("Bill From identifiers")}
                  identifiers={detail.vendor_identifiers}
                />
                <IssuedIdentifiers
                  title={t("Bill To identifiers")}
                  identifiers={detail.client_identifiers}
                />
              </div>
            )}
          </section>

          <Separator />
          <section className="flex flex-col gap-4">
            <SectionHeading step={4} title={t("Payment")} />
            <PaymentSection
              form={form}
              accounts={context?.payee_accounts ?? []}
              invoiceCurrency={context?.currency_code ?? null}
              paymentTerms={paymentTerms}
              dueDate={dueDate}
              today={today}
              readOnly={readOnly}
              detail={detail}
              onTermsChange={({ paymentTerms: terms, dueDate: date }) => {
                setValue("payment_terms", terms, { shouldDirty: true });
                setValue("due_date", date, { shouldDirty: true });
              }}
            />
          </section>

          <Separator />
          <section className="flex flex-col gap-4">
            <SectionHeading step={5} title={t("Line items")} />
            {!readOnly && (
              <GenerateLinesGroup
                canGenerate={canGenerate && busy === null}
                generating={busy === "generating"}
                onGenerate={() => void runGenerate()}
              >
                {context && isFixedPrice && (
                  <MilestoneBillingPanel
                    milestones={context.milestones}
                    selected={milestoneIds}
                    onSelectedChange={setMilestoneIds}
                    currencyCode={context.currency_code}
                    minorUnit={context.currency_minor_unit}
                    disabled={readOnly}
                  />
                )}
                {context && !isFixedPrice && (
                  <TmBillingPanel
                    serviceLines={context.service_lines}
                    selected={serviceLineIds}
                    onSelectedChange={(ids) => setValue("service_line_ids", ids)}
                    period={{ preset: periodPreset, start: periodStart, end: periodEnd }}
                    onPeriodChange={(period) => {
                      setValue("period_preset", period.preset);
                      setValue("period_start", period.start, { shouldDirty: true });
                      setValue("period_end", period.end, { shouldDirty: true });
                    }}
                    minorUnit={context.currency_minor_unit}
                    today={today}
                    disabled={readOnly}
                  />
                )}
              </GenerateLinesGroup>
            )}
            <InvoiceLinesTable
              form={form}
              currencyCode={
                readOnly ? (detail?.currency_code ?? null) : (context?.currency_code ?? null)
              }
              minorUnit={
                readOnly
                  ? (detail?.currency_minor_unit ?? null)
                  : (context?.currency_minor_unit ?? null)
              }
              disabled={readOnly}
            />
            <InvoiceTaxesTable
              form={form}
              currencyCode={
                readOnly ? (detail?.currency_code ?? null) : (context?.currency_code ?? null)
              }
              minorUnit={
                readOnly
                  ? (detail?.currency_minor_unit ?? null)
                  : (context?.currency_minor_unit ?? null)
              }
              disabled={readOnly}
              stored={readOnly && detail ? { taxes: detail.taxes, total: detail.total } : null}
            />
            {!readOnly && (
              <InvoiceWarnings
                warnings={warnings}
                omitted={omitted}
                minorUnit={context?.currency_minor_unit ?? null}
              />
            )}
          </section>
        </>
      )}

      {formError && <p className="text-destructive text-sm">{formError}</p>}

      <div className="flex flex-wrap justify-end gap-2">
        {invoiceId && !readOnly && (
          <Button
            type="button"
            variant="outline"
            className="text-destructive"
            disabled={busy !== null}
            onClick={() => setConfirmDelete(true)}
          >
            {t("Delete draft")}
          </Button>
        )}
        {readOnly && (
          <Button
            type="button"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void handleDuplicate()}
          >
            {busy === "duplicating" && <Spinner />}
            {t("Duplicate", { ns: "common" })}
          </Button>
        )}
        {status === "issued" && (
          <Button
            type="button"
            variant="outline"
            className="text-destructive"
            disabled={busy !== null}
            onClick={() => setVoidOpen(true)}
          >
            {t("Void")}
          </Button>
        )}
        <Button type="button" variant="outline" onClick={() => navigate("/invoices")}>
          {t("Close", { ns: "common" })}
        </Button>
        {!readOnly && (
          <Button type="submit" variant="outline" disabled={busy !== null || !projectId}>
            {busy === "saving" && <Spinner />}
            {busy === "saving" ? t("Saving…", { ns: "common" }) : t("Save draft")}
          </Button>
        )}
        {!readOnly && (
          <Button
            type="button"
            disabled={
              busy !== null || !projectId || !!preview?.blocking.includes("project_not_active")
            }
            onClick={() => void handleIssue()}
          >
            {t("Issue")}
          </Button>
        )}
      </div>

      <IssueInvoiceDialog
        open={issueOpen}
        onOpenChange={setIssueOpen}
        preview={preview}
        minorUnit={context?.currency_minor_unit ?? null}
        issuing={busy === "issuing"}
        onConfirm={() => void confirmIssue()}
      />
      <VoidInvoiceDialog
        open={voidOpen}
        onOpenChange={setVoidOpen}
        number={detail?.number ?? ""}
        voiding={busy === "voiding"}
        onConfirm={(reason) => void confirmVoid(reason)}
      />

      <AlertDialog
        open={pendingProject !== null}
        onOpenChange={(open) => !open && setPendingProject(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Change the project?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "The line items are cleared, and the parties, payee account, references and service lines are filled in again from the new project.",
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("Cancel", { ns: "common" })}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingProject) void applyProject(pendingProject);
                setPendingProject(null);
              }}
            >
              {t("Change project")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("Delete the draft for {{project}}?", {
                project: context?.name ?? savedProjectName ?? "",
              })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("The draft and its lines are removed for good.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy === "deleting"}>
              {t("Cancel", { ns: "common" })}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={busy === "deleting"}
              onClick={() => void handleDelete()}
            >
              {busy === "deleting" && <Spinner />}
              {busy === "deleting"
                ? t("Deleting…", { ns: "common" })
                : t("Delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  );
}
