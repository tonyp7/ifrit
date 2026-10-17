import { toast } from "sonner";

import type { SettingSaveResult } from "@/hooks/useSettingField";

/**
 * Turns a setting save into a toast: a rejection carries the server's reason, and a failed
 * request says nothing about the value, so it gets a message of its own.
 */
export function reportSettingSave(
  result: SettingSaveResult | null,
  successMessage: string,
  networkMessage: string,
) {
  if (result === null) return;
  if (result.ok) toast.success(successMessage);
  else if (result.rejected) toast.error(result.message);
  else toast.error(networkMessage);
}
