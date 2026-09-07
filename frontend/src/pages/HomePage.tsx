import { useTranslation } from "react-i18next";

import { useAuth } from "@/hooks/useAuth";

// Post-login landing screen — first nav bar item, shown to every role regardless of
// which other screens they can access. Currently an empty placeholder; will later
// host generic information and/or widgets and/or a dashboard (see
// specs/requirements/home.md).
export function HomePage() {
  const { user } = useAuth();
  const { t } = useTranslation(["home"]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-2 p-4 text-center">
      <p className="text-lg font-medium">
        {t("Welcome, {{name}}.", { name: user?.full_name })}
      </p>
      <p className="text-sm text-muted-foreground">
        {t("This is a placeholder — the home dashboard isn't built yet.")}
      </p>
    </div>
  );
}
