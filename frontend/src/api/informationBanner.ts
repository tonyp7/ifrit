import { apiClient } from "@/api/client";
import type { PublicBanner } from "@/types/settings";

/** The banner for each place it can show. Needs no sign-in, so the login page can use it. */
export function getInformationBanner() {
  return apiClient.get<PublicBanner>("/information-banner");
}
