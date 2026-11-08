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
  { code: "zh-CN", nativeName: "简体中文" },
];

export const FALLBACK_LANGUAGE = "en";

/**
 * The languages i18next may load, so a regional code such as `zh-CN` is never also looked up as
 * its base `zh`. That folder does not exist, and the web server answers any unknown path with the
 * app's `index.html`, which would arrive as a successful response holding HTML, not JSON.
 */
export const I18N_LANGUAGE_OPTIONS = {
  supportedLngs: SUPPORTED_LANGUAGES.map((language) => language.code),
};

/** Where an explicit choice is kept. Browser-only on purpose: the sign-in screen has to be in
 * the right language before anyone is authenticated, and nothing about it follows a user to
 * another device. */
export const LANGUAGE_STORAGE_KEY = "ifrit.language";

function isSupported(code: string): boolean {
  return SUPPORTED_LANGUAGES.some((language) => language.code === code);
}

/** The language and script a tag stands for once its omitted parts are filled in, so `zh`,
 * `zh-CN` and `zh-Hans-SG` all read `zh-Hans`, while `zh-TW` and `zh-Hant` read `zh-Hant`, and
 * `fr-CA` reads `fr-Latn`. Null for a tag that is not valid. */
function languageAndScript(tag: string): string | null {
  try {
    const { language, script } = new Intl.Locale(tag.trim().replace(/_/g, "-")).maximize();
    return `${language}-${script}`;
  } catch {
    return null;
  }
}

/**
 * The offered language a browser tag stands for, or null. It is the same language and the same
 * script, not just the same base language: Traditional Chinese (`zh-TW`) must not select an
 * offered Simplified Chinese, whose readers it does not serve, so it matches nothing and the
 * search goes on down the browser's list.
 */
function toSupported(tag: string): string | null {
  const wanted = languageAndScript(tag);
  if (!wanted) return null;
  const match = SUPPORTED_LANGUAGES.find(
    (language) => languageAndScript(language.code) === wanted,
  );
  return match ? match.code : null;
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
  const storedCode = SUPPORTED_LANGUAGES.find(
    (language) => language.code.toLowerCase() === stored?.trim().toLowerCase(),
  )?.code;
  if (storedCode) return storedCode;
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
