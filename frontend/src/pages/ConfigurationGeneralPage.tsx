import { useTranslation } from "react-i18next";

import { PlaceholderScreen } from "@/components/PlaceholderScreen";

export function ConfigurationGeneralPage() {
  const { t } = useTranslation(["common"]);

  return <PlaceholderScreen title={t("General")} />;
}
