import { useEffect, useState } from "react";

import { getInformationBanner } from "@/api/informationBanner";
import type { PublicBanner } from "@/types/settings";

/**
 * The banner, or null when there is none to show or it could not be read. A failure is
 * deliberately silent: the banner is optional information and must never get in the way of
 * signing in or using a page.
 */
export async function loadBanner(
  read: () => Promise<PublicBanner>,
): Promise<PublicBanner | null> {
  try {
    return await read();
  } catch {
    return null;
  }
}

/**
 * Reads the banner once, when the component using it first appears, and never again until
 * it appears anew (a page reload, or signing in). A banner switched on while a page is
 * open therefore shows on the next full load.
 */
export function useInformationBanner(): PublicBanner | null {
  const [banner, setBanner] = useState<PublicBanner | null>(null);

  useEffect(() => {
    let cancelled = false;
    void loadBanner(getInformationBanner).then((result) => {
      if (!cancelled) setBanner(result);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return banner;
}
