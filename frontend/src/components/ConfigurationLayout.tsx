import { Suspense } from "react";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useLocation } from "react-router-dom";

import { PageLoadErrorBoundary } from "@/components/PageLoadErrorBoundary";
import { PageLoading } from "@/components/PageLoading";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CONFIGURATION_TABS, configurationTabForPath } from "@/config/configurationTabs";

// Shared frame for every /configuration screen. The tabs are real links (asChild) rather
// than state, so each section is directly addressable and openable in a new browser tab,
// and the active one comes from the URL so it can't drift from the address. Choosing a tab
// from a form screen simply navigates away, discarding the form like its Cancel button.
export function ConfigurationLayout() {
  const { t } = useTranslation(["common"]);
  const { pathname } = useLocation();

  return (
    <div>
      {/* Each screen below supplies its own padding, so only the top and sides here. */}
      <Tabs value={configurationTabForPath(pathname)} className="px-4 pt-4">
        <TabsList>
          {CONFIGURATION_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} asChild>
              <Link to={`/configuration/${tab.value}`}>{t(tab.label)}</Link>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {/* The tab bar stays while a tab's page downloads or fails to: without a boundary here
          the nearest one is the app-wide layout's, which would replace this whole area. */}
      <PageLoadErrorBoundary resetKey={pathname}>
        <Suspense fallback={<PageLoading />}>
          <Outlet />
        </Suspense>
      </PageLoadErrorBoundary>
    </div>
  );
}
