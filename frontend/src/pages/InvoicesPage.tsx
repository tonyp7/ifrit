import { useTranslation } from "react-i18next";

// Invoices cannot be created yet, so the screen is only its empty state: no list, no
// create action.
export function InvoicesPage() {
  const { t } = useTranslation(["invoices"]);

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-medium">{t("Invoices")}</h1>
      <p className="text-muted-foreground py-8 text-center text-sm">{t("No invoices yet")}</p>
    </div>
  );
}
