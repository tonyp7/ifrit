import { useTranslation } from "react-i18next";

import { PlaceholderScreen } from "@/components/PlaceholderScreen";

export function TimesheetPage() {
  const { t } = useTranslation(["timesheet"]);
  return <PlaceholderScreen title={t("Timesheet")} />;
}
