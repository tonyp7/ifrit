import { Suspense } from "react";
import { Outlet, useLocation } from "react-router";

import {
  InformationBannerProvider,
  SiteWideBanner,
} from "@/components/InformationBannerProvider";
import { NavBar } from "@/components/NavBar";
import { PageLoadErrorBoundary } from "@/components/PageLoadErrorBoundary";
import { PageLoading } from "@/components/PageLoading";

export function AppLayout() {
  const { pathname } = useLocation();

  return (
    <InformationBannerProvider>
      <div className="min-h-screen">
        <NavBar />
        <main className="min-h-screen pb-14 md:pb-0 md:pl-14">
          {/* First inside <main>, so it sits beside the navigation rail and above the bottom bar
            like the page does, and scrolls away with it. It has no close control. */}
          <SiteWideBanner />
          {/* Pages other than the timesheet are downloaded on first visit: the navigation bar
            above stays on screen while one loads, and a page that fails to download shows a
            message here instead of leaving a blank screen. */}
          <PageLoadErrorBoundary resetKey={pathname}>
            <Suspense fallback={<PageLoading />}>
              <Outlet />
            </Suspense>
          </PageLoadErrorBoundary>
        </main>
      </div>
    </InformationBannerProvider>
  );
}
