import { Download, Upload } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { formatFileSize } from "@/lib/format";
import type {
  InvoiceTemplateInfo,
  TemplateFinding,
  TemplateToken,
} from "@/types/invoiceTemplate";

// What the file chooser offers; the server checks the real content.
const ACCEPTED_TYPES = ".odt,application/vnd.oasis.opendocument.text";

/** What the card is showing about a file the administrator has chosen and not yet
 * confirmed. */
export type TemplateReview =
  | { fileName: string; status: "checking" }
  | { fileName: string; status: "ready"; pdfUrl: string; warnings: TemplateFinding[] }
  | {
      fileName: string;
      status: "rejected";
      problems: TemplateFinding[];
      warnings: TemplateFinding[];
    }
  | { fileName: string; status: "failed"; message: string };

export interface InvoiceTemplateCardViewProps {
  info: InvoiceTemplateInfo | null;
  /** True until the template in use has been read, whatever the outcome. */
  loading: boolean;
  loadFailed: boolean;
  tokens: TemplateToken[] | null;
  review: TemplateReview | null;
  saving: boolean;
  resetting: boolean;
  downloading: boolean;
  onChooseFile: (file: File) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onReset: () => void;
  onDownload: () => void;
}

function Findings({ items }: { items: TemplateFinding[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {items.map((item, index) => (
        <li key={`${item.part}-${index}`}>
          <span className="text-muted-foreground">{item.part}: </span>
          {item.message}
          {item.snippet && <code className="bg-muted ml-1 rounded px-1">{item.snippet}</code>}
        </li>
      ))}
    </ul>
  );
}

export function InvoiceTemplateCardView({
  info,
  loading,
  loadFailed,
  tokens,
  review,
  saving,
  resetting,
  downloading,
  onChooseFile,
  onConfirm,
  onCancel,
  onReset,
  onDownload,
}: InvoiceTemplateCardViewProps) {
  const { t } = useTranslation(["configuration", "common"]);
  const inputRef = useRef<HTMLInputElement>(null);
  const checking = review?.status === "checking";
  const busy = loading || loadFailed || checking || saving || resetting;
  const isDefault = info?.source !== "custom";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("Invoice Template")}</CardTitle>
        <CardDescription>
          {t(
            "The layout invoice PDFs are made from. Download it, edit it in LibreOffice Writer, and upload it again.",
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loadFailed && (
          <Alert variant="destructive">
            <AlertDescription>{t("Couldn't load the invoice template.")}</AlertDescription>
          </Alert>
        )}

        {info && (
          <p className="text-sm" data-testid="template-state">
            {info.source === "default" ? (
              t("Default template")
            ) : (
              <>
                <span className="font-medium">{info.filename}</span>
                <span className="text-muted-foreground">
                  {" · "}
                  {formatFileSize(info.size_bytes)}
                  {info.uploaded_by_name &&
                    info.uploaded_at &&
                    ` · ${t("Uploaded by {{name}} on {{date}}", {
                      name: info.uploaded_by_name,
                      date: new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(info.uploaded_at)),
                    })}`}
                </span>
              </>
            )}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="hidden"
            data-testid="template-file-input"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Cleared so choosing the same file again (after a fix) still fires.
              event.target.value = "";
              if (file) onChooseFile(file);
            }}
          />
          <Button
            type="button"
            variant="outline"
            disabled={busy || downloading}
            onClick={onDownload}
          >
            {downloading ? <Spinner /> : <Download className="h-4 w-4" aria-hidden="true" />}
            {t("Download")}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-4 w-4" aria-hidden="true" />
            {t("Upload…")}
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button type="button" variant="ghost" disabled={busy || isDefault}>
                {resetting && <Spinner />}
                {t("Reset to default")}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("Reset to the default template?")}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t(
                    "The uploaded template will be discarded. Invoices already issued keep their PDF.",
                  )}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t("Cancel", { ns: "common" })}</AlertDialogCancel>
                <AlertDialogAction onClick={onReset}>
                  {t("Reset to default")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>

        {review && (
          <section
            className="flex flex-col gap-3 rounded-md border p-4"
            aria-label={t("Uploaded template")}
          >
            <h3 className="text-sm font-medium">{review.fileName}</h3>

            {review.status === "checking" && (
              <p className="text-muted-foreground flex items-center gap-2 text-sm">
                <Spinner />
                {t("Checking the template and making a sample PDF…")}
              </p>
            )}

            {review.status === "failed" && (
              <Alert variant="destructive">
                <AlertDescription>{review.message}</AlertDescription>
              </Alert>
            )}

            {review.status === "rejected" && (
              <Alert variant="destructive">
                <AlertTitle>{t("This template cannot be used")}</AlertTitle>
                <AlertDescription>
                  <Findings items={review.problems} />
                </AlertDescription>
              </Alert>
            )}

            {(review.status === "ready" || review.status === "rejected") &&
              review.warnings.length > 0 && (
                <Alert>
                  <AlertTitle>{t("Warnings")}</AlertTitle>
                  <AlertDescription>
                    <Findings items={review.warnings} />
                  </AlertDescription>
                </Alert>
              )}

            {review.status === "ready" && (
              <>
                <p className="text-muted-foreground text-sm">
                  {t(
                    "This is how it looks with sample data. Nothing changes until you confirm.",
                  )}
                </p>
                <iframe
                  title={t("Sample invoice")}
                  src={review.pdfUrl}
                  className="h-[28rem] w-full rounded-md border"
                />
                <a
                  href={review.pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm underline"
                >
                  {t("Open the sample in a new tab")}
                </a>
              </>
            )}

            <div className="flex flex-wrap gap-2">
              {review.status === "ready" && (
                <Button type="button" disabled={saving} onClick={onConfirm}>
                  {saving && <Spinner />}
                  {t("Use this template")}
                </Button>
              )}
              <Button type="button" variant="outline" disabled={saving} onClick={onCancel}>
                {review.status === "ready"
                  ? t("Cancel", { ns: "common" })
                  : t("Close", { ns: "common" })}
              </Button>
            </div>
          </section>
        )}

        <details className="text-sm">
          <summary className="cursor-pointer font-medium">{t("Placeholders")}</summary>
          <p className="text-muted-foreground mt-2">
            {t(
              "Type a placeholder such as {{example}} in the template. Add a ? ({{optional}}) to drop its paragraph when it is empty.",
              { example: "{{invoice_number}}", optional: "{{payee_bank_name?}}" },
            )}
          </p>
          {tokens ? (
            <table className="mt-2 w-full text-left">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="py-1 pr-4 font-normal">{t("Placeholder")}</th>
                  <th className="py-1 pr-4 font-normal">{t("Meaning")}</th>
                  <th className="py-1 font-normal">{t("Example")}</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((token) => (
                  <tr key={token.name} className="border-t align-top">
                    <td className="py-1 pr-4">
                      <code>{`{{${token.name}}}`}</code>
                    </td>
                    <td className="py-1 pr-4">{token.description}</td>
                    <td className="py-1">{token.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-muted-foreground mt-2">{t("Loading…", { ns: "common" })}</p>
          )}
        </details>
      </CardContent>
    </Card>
  );
}
