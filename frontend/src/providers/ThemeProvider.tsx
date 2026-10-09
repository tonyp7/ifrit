import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { updateThemePreference } from "@/api/users";
import { useAuth } from "@/hooks/useAuth";
import { ThemeContext, type ResolvedTheme } from "@/providers/themeContext";
import type { ThemePreference } from "@/types/user";

const DARK_SCHEME_QUERY = "(prefers-color-scheme: dark)";

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia(DARK_SCHEME_QUERY).matches ? "dark" : "light";
}

function subscribeToSystemTheme(onChange: () => void) {
  const media = window.matchMedia(DARK_SCHEME_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  // No authenticated user yet (e.g. the login screen) -> always System, no override:
  // there's nowhere to read/store a persisted preference from until logged in.
  const [themePreference, setThemePreferenceState] = useState<ThemePreference>(
    user?.theme_preference ?? "system",
  );

  // Re-sync whenever the authenticated user changes (login, logout, session restore). Done
  // while rendering, by comparing with the user last synced from, rather than in an effect:
  // an effect would first render with the stale preference and then render again.
  const [syncedUser, setSyncedUser] = useState(user);
  if (user !== syncedUser) {
    setSyncedUser(user);
    setThemePreferenceState(user?.theme_preference ?? "system");
  }

  // The OS colour scheme is an external value, so it is read through a subscription. The
  // resolved theme is then derived from it and the preference instead of being stored.
  const systemTheme = useSyncExternalStore(subscribeToSystemTheme, getSystemTheme);
  const resolvedTheme: ResolvedTheme = themePreference === "system" ? systemTheme : themePreference;

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
