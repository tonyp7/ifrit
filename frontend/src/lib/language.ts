import i18n from "i18next";

export interface SupportedLanguage {
  code: string;
  /** The language's own name: it must read the same whatever language the UI is in, so it
   * is a constant, not a translation key. */
  nativeName: string;
}

export const SUPPORTED_LANGUAGES: readonly SupportedLanguage[] = [
  { code: "en", nativeName: "English" },
  { code: "fr", nativeName: "Français" },
];

export const FALLBACK_LANGUAGE = "en";

/** Where an explicit choice is kept. Browser-only on purpose: the sign-in screen has to be in
 * the right language before anyone is authenticated, and nothing about it follows a user to
 * another device. */
export const LANGUAGE_STORAGE_KEY = "ifrit.language";

function isSupported(code: string): boolean {
  return SUPPORTED_LANGUAGES.some((language) => language.code === code);
}

/** `fr-CA` and `fr_CA` give `fr`; anything that is not a supported base language gives null. */
function toSupported(tag: string): string | null {
  const base = tag.trim().toLowerCase().split(/[-_]/)[0];
  return isSupported(base) ? base : null;
}

/**
 * The language to start in: the stored choice if it is an offered language, otherwise the
 * first browser preference that is, otherwise English. A stored value is matched exactly
 * (case aside) so a stale or hand-edited value is ignored rather than guessed at.
 */
export function resolveLanguage(
  stored: string | null | undefined,
  browserLanguages: readonly string[],
): string {
  const storedCode = stored?.trim().toLowerCase();
  if (storedCode && isSupported(storedCode)) return storedCode;
  for (const tag of browserLanguages) {
    const match = toSupported(tag);
    if (match) return match;
  }
  return FALLBACK_LANGUAGE;
}

// Storage can throw (private windows, blocked site data), so every access is guarded and the
// app simply works for the session in the detected language.
export function readStoredLanguage(): string | null {
  try {
    return window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredLanguage(code: string): void {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
  } catch {
    // Not remembered across reloads; nothing else depends on it.
  }
}

export function detectLanguage(): string {
  const preferred =
    typeof navigator === "undefined"
      ? []
      : navigator.languages?.length
        ? navigator.languages
        : [navigator.language];
  return resolveLanguage(readStoredLanguage(), preferred.filter(Boolean));
}

/** The page's own `lang` attribute, which screen readers and the browser's hyphenation and
 * translation prompts read. */
export function applyDocumentLanguage(code: string): void {
  if (typeof document !== "undefined") document.documentElement.lang = code;
}

/** Switches every screen at once and remembers the choice in this browser. */
export async function setLanguage(code: string): Promise<void> {
  if (!isSupported(code)) return;
  writeStoredLanguage(code);
  await i18n.changeLanguage(code);
}

/**
 * The locale every number, date and sort-order formatter uses. It is the app language, not the
 * browser's regional settings, so a French screen never shows English dates or the reverse.
 */
export function currentLocale(): string {
  return i18n.resolvedLanguage ?? i18n.language ?? FALLBACK_LANGUAGE;
}
