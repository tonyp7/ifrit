import { createContext, useContext } from "react";

import { loadBanner } from "@/hooks/useInformationBanner";
import type { SettingSaveResult } from "@/hooks/useSettingField";
import type { PublicBanner } from "@/types/settings";

export interface InformationBannerContextValue {
  /** The banner last read for the signed-in area; null until the first read succeeds. */
  banner: PublicBanner | null;
  /** Reads the banner again. */
  refresh: () => void;
}

// Outside a provider (the card in a test, say) there is nothing to refresh.
export const InformationBannerContext = createContext<InformationBannerContextValue>({
  banner: null,
  refresh: () => {},
});

export function useInformationBannerContext(): InformationBannerContextValue {
  return useContext(InformationBannerContext);
}

/**
 * A reader that only ever hands back the answer of the newest request it was asked to make:
 * a slow earlier answer arriving after a later one resolves to null, as does a failed
 * request, so a caller that keeps what it has on null can never go back to older data.
 */
export function createBannerLoader(
  read: () => Promise<PublicBanner>,
): () => Promise<PublicBanner | null> {
  let newest = 0;
  return async () => {
    const mine = ++newest;
    const result = await loadBanner(read);
    return mine === newest ? result : null;
  };
}

/**
 * Called with the outcome of a save in the settings card: only a save the server accepted
 * can have changed what visitors see. A rejected or failed one, or one that sent nothing
 * (null), leaves the strip alone.
 */
export function refreshAfterSave(result: SettingSaveResult | null, refresh: () => void) {
  if (result?.ok) refresh();
}
