import { useTranslation } from "react-i18next";

export function PlaceholderScreen({ title }: { title: string }) {
  const { t } = useTranslation(["common"]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 p-4 text-center">
      <p className="text-lg font-medium">{title}</p>
      <p className="text-sm text-muted-foreground">{t("Not built yet.")}</p>
    </div>
  );
}
