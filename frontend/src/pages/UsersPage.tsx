import { useTranslation } from "react-i18next";

import { UsersTable } from "@/components/users/UsersTable";

export function UsersPage() {
  const { t } = useTranslation(["user"]);

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-medium">{t("Users")}</h1>
      <UsersTable />
    </div>
  );
}
