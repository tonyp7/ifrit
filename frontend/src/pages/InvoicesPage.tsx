import { useTranslation } from "react-i18next";

import { InvoicesTable } from "@/components/invoices/InvoicesTable";

export function InvoicesPage() {
  const { t } = useTranslation(["invoices"]);

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-medium">{t("Invoices")}</h1>
      <InvoicesTable />
    </div>
  );
}
