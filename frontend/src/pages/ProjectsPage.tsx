import { useTranslation } from "react-i18next";

import { ProjectsTable } from "@/components/projects/ProjectsTable";

export function ProjectsPage() {
  const { t } = useTranslation(["projects"]);

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-lg font-medium">{t("Projects")}</h1>
      <ProjectsTable />
    </div>
  );
}
