import { useTranslation } from "react-i18next";

import { CompaniesTable } from "@/components/companies/CompaniesTable";

export function CompaniesListPage() {
  const { t } = useTranslation(["company"]);

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-medium">{t("Companies")}</h1>
      <CompaniesTable />
    </div>
  );
}
