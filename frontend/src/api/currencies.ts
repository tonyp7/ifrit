import { apiClient } from "@/api/client";
import type { Currency } from "@/types/currency";

export function listCurrencies() {
  return apiClient.get<Currency[]>("/currencies");
}
