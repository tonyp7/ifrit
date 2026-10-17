import { AlertTriangle, Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useServiceLineLabel } from "@/hooks/useServiceLineLabel";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { InvoiceWarning, OmittedServiceLine } from "@/types/invoice";

interface InvoiceWarningsProps {
  warnings: InvoiceWarning[];
  /** Selected service lines that had no hours in the period, from the last generation. */
  omitted: OmittedServiceLine[];
  minorUnit: number | null;
}

/** Warnings never block saving; each carries an icon and text, not colour alone. */
export function InvoiceWarnings({ warnings, omitted, minorUnit }: InvoiceWarningsProps) {
  const { t } = useTranslation(["invoices"]);
  const label = useServiceLineLabel(minorUnit);

  function message(warning: InvoiceWarning): string {
    switch (warning.code) {
      case "unlocked_hours":
        return t("Unlocked hours: {{lines}}. The amounts could still change after issuing.", {
          lines: warning.service_lines
            .map((line) =>
              t("{{name}} ({{count}} days)", { name: label(line), count: line.days }),
            )
            .join(", "),
        });
      case "zero_quantity":
        return t("Zero-quantity line: a line has quantity 0.");
      case "no_payee_account":
        return t("No payee account: the invoice does not say which account to pay into.");
      case "payee_currency":
        return t("Payee account currency: the payee account is not in the invoice currency.");
      case "inactive_company":
        return warning.companies.includes("vendor") && warning.companies.includes("client")
          ? t("Inactive company: the project's vendor and client have been deactivated.")
          : warning.companies.includes("vendor")
            ? t("Inactive company: the project's vendor has been deactivated.")
            : t("Inactive company: the project's client has been deactivated.");
      case "due_before_invoice_date":
        return t(
          "Due date before the invoice date: the invoice would be overdue when issued.",
        );
    }
  }

  if (warnings.length === 0 && omitted.length === 0) return null;

  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      {omitted.length > 0 && (
        <Alert>
          <Info className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            {t("No hours in the period, left out: {{lines}}.", {
              lines: omitted.map((line) => label(line)).join(", "),
            })}
          </AlertDescription>
        </Alert>
      )}
      {warnings.map((warning) => (
        <Alert key={warning.code}>
          <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
          <AlertDescription>{message(warning)}</AlertDescription>
        </Alert>
      ))}
    </div>
  );
}
