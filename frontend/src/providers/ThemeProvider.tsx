import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { updateThemePreference } from "@/api/users";
import { useAuth } from "@/hooks/useAuth";
import { ThemeContext, type ResolvedTheme } from "@/providers/themeContext";
import type { ThemePreference } from "@/types/user";

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === "system" ? getSystemTheme() : preference;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  // No authenticated user yet (e.g. the login screen) -> always System, no override:
  // there's nowhere to read/store a persisted preference from until logged in.
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>(
    user?.theme_preference ?? "system",
  );

  // Re-sync whenever the authenticated user changes (login, logout, session restore).
  useEffect(() => {
    setThemePreferenceState(user?.theme_preference ?? "system");
  }, [user]);

  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    resolveTheme(themePreference),
  );

  useEffect(() => {
    setResolvedTheme(resolveTheme(themePreference));

    if (themePreference !== "system") return;

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolvedTheme(getSystemTheme());
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [themePreference]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
  }, [resolvedTheme]);

  const setThemePreference = useCallback(
    async (preference: ThemePreference) => {
      setThemePreferenceState(preference);
      if (!user) return;
      try {
        await updateThemePreference(preference);
      } catch (err) {
        console.error("Failed to persist theme preference", err);
      }
    },
    [user],
  );

  const value = useMemo(
    () => ({ themePreference, resolvedTheme, setThemePreference }),
    [themePreference, resolvedTheme, setThemePreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
