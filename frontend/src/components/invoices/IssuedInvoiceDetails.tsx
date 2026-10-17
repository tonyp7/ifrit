import { useTranslation } from "react-i18next";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { formatDueDate } from "@/lib/billingMilestones";
import { ID_TYPE_LABELS } from "@/types/company";
import {
  INVOICE_STATUS_LABELS,
  PAYMENT_TERMS_LABELS,
  type InvoiceDetail,
  type InvoiceStatus,
  type IssuePreview,
  type SnapshotIdentifier,
} from "@/types/invoice";

// The parts of the invoice page that show what issuing set: the heading, the banner that
// stops a draft from being issued, the void notice, and the frozen dates and identifiers.

const STATUS_VARIANT = { draft: "secondary", issued: "default", void: "outline" } as const;

export function InvoiceHeading({
  status,
  detail,
  preview,
  isNew,
}: {
  status: InvoiceStatus;
  detail: InvoiceDetail | null;
  preview: IssuePreview | null;
  isNew: boolean;
}) {
  const { t } = useTranslation(["invoices"]);
  const issued = status !== "draft" && detail?.number;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h1 className="text-lg font-medium">
        {issued ? (
          <>
            {detail.document_name && (
              <span className="text-muted-foreground mr-2 font-normal">
                {detail.document_name}
              </span>
            )}
            <span className="font-mono">{detail.number}</span>
          </>
        ) : isNew ? (
          t("New invoice")
        ) : (
          t("Edit invoice")
        )}
      </h1>
      <Badge variant={STATUS_VARIANT[status]}>{t(INVOICE_STATUS_LABELS[status])}</Badge>
      {status === "draft" && (
        <span className="text-muted-foreground text-sm" data-testid="likely-number">
          {preview
            ? t("Likely number {{number}}, assigned when issued", { number: preview.number })
            : t("Number assigned when issued")}
        </span>
      )}
    </div>
  );
}

/** Shown on a draft whose project is no longer Active: it can be edited but not issued. */
export function ProjectNotActiveBanner({ preview }: { preview: IssuePreview }) {
  const { t } = useTranslation(["invoices"]);
  if (!preview.blocking.includes("project_not_active")) return null;
  return (
    <Alert variant="destructive">
      <AlertDescription>
        {t("This invoice cannot be issued because its project is not Active.")}
      </AlertDescription>
    </Alert>
  );
}

export function VoidNotice({ detail }: { detail: InvoiceDetail }) {
  const { t } = useTranslation(["invoices"]);
  return (
    <Alert>
      <AlertDescription>
        {t("Voided by {{name}} on {{date}}.", {
          name: detail.voided_by_name ?? t("a user who no longer exists"),
          date: detail.voided_at ? new Date(detail.voided_at).toLocaleString() : "",
        })}
        {detail.void_reason && ` ${t("Reason: {{reason}}", { reason: detail.void_reason })}`}
      </AlertDescription>
    </Alert>
  );
}

/** The invoice and due dates as frozen at issue, with the preset in brackets when one was
 * used, e.g. "13 Nov 2026 (Net 30)". */
export function IssuedDates({ detail }: { detail: InvoiceDetail }) {
  const { t } = useTranslation(["invoices"]);
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      <dt className="text-muted-foreground">{t("Invoice date")}</dt>
      <dd>{detail.invoice_date ? formatDueDate(detail.invoice_date) : ""}</dd>
      <dt className="text-muted-foreground">{t("Due date")}</dt>
      <dd data-testid="issued-due">
        {detail.due_date ? formatDueDate(detail.due_date) : t("None")}
        {detail.payment_terms && ` (${t(PAYMENT_TERMS_LABELS[detail.payment_terms])})`}
      </dd>
    </dl>
  );
}

/** A party's identifiers as frozen at issue. */
export function IssuedIdentifiers({
  title,
  identifiers,
}: {
  title: string;
  identifiers: SnapshotIdentifier[];
}) {
  const { t } = useTranslation(["invoices", "company"]);
  return (
    <div className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{title}</span>
      {identifiers.length === 0 ? (
        <span className="text-muted-foreground">{t("No identifiers")}</span>
      ) : (
        <ul>
          {identifiers.map((identifier) => (
            <li key={`${identifier.id_type}-${identifier.id_value}`}>
              {t(ID_TYPE_LABELS[identifier.id_type], { ns: "company" })}:{" "}
              <span className="font-mono">
                {identifier.scheme_id ? `${identifier.scheme_id}:` : ""}
                {identifier.id_value}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
