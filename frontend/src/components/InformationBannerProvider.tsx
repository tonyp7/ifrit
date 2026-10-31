import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { getInformationBanner } from "@/api/informationBanner";
import { InformationBanner } from "@/components/InformationBanner";
import {
  createBannerLoader,
  InformationBannerContext,
  useInformationBannerContext,
} from "@/hooks/informationBannerContext";
import type { PublicBanner } from "@/types/settings";

/**
 * Holds the banner for the signed-in area. It reads once when it first appears, and again
 * whenever `refresh` is called, which the settings card does after an administrator's own
 * save so that the strip shows what was just saved. Everyone else reads once per page load.
 */
export function InformationBannerProvider({ children }: { children: ReactNode }) {
  const [banner, setBanner] = useState<PublicBanner | null>(null);
  const loader = useMemo(() => createBannerLoader(getInformationBanner), []);
  const mounted = useRef(false);

  const refresh = useCallback(() => {
    void loader().then((result) => {
      // null is a failed or outdated read: keep what is shown.
      if (result && mounted.current) setBanner(result);
    });
  }, [loader]);

  useEffect(() => {
    mounted.current = true;
    refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  const value = useMemo(() => ({ banner, refresh }), [banner, refresh]);
  return <InformationBannerContext value={value}>{children}</InformationBannerContext>;
}

/** The strip across the top of the signed-in content; nothing when there is no banner. */
export function SiteWideBanner() {
  const site = useInformationBannerContext().banner?.site_wide ?? null;
  if (!site) return null;
  return <InformationBanner {...site} className="rounded-none border-x-0 border-t-0" />;
}
