import { createContext } from "react";

import type { ThemePreference } from "@/types/user";

export type ResolvedTheme = "light" | "dark";

export interface ThemeContextValue {
  themePreference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setThemePreference: (preference: ThemePreference) => Promise<void>;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
