import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  currentLocale,
  LANGUAGE_STORAGE_KEY,
  readStoredLanguage,
  resolveLanguage,
  setLanguage,
  SUPPORTED_LANGUAGES,
} from "@/lib/language";

describe("resolveLanguage", () => {
  it("prefers a stored choice over the browser", () => {
    expect(resolveLanguage("en", ["fr-FR"])).toBe("en");
    expect(resolveLanguage("fr", ["en-US"])).toBe("fr");
  });

  it("ignores a stored value that is not an offered language", () => {
    expect(resolveLanguage("de", ["fr"])).toBe("fr");
    expect(resolveLanguage("fr-FR", ["en"])).toBe("en");
    expect(resolveLanguage("", [])).toBe("en");
  });

  it("matches a regional variant to its base language", () => {
    expect(resolveLanguage(null, ["fr-CA"])).toBe("fr");
    expect(resolveLanguage(null, ["FR_be"])).toBe("fr");
  });

  it("takes the first browser preference the app offers", () => {
    expect(resolveLanguage(null, ["de-DE", "fr-FR", "en"])).toBe("fr");
    expect(resolveLanguage(null, ["en-GB", "fr"])).toBe("en");
  });

  it("falls back to English", () => {
    expect(resolveLanguage(null, ["de"])).toBe("en");
    expect(resolveLanguage(undefined, [])).toBe("en");
  });
});

describe("offered languages", () => {
  it("names each language in itself", () => {
    expect(SUPPORTED_LANGUAGES.map((l) => [l.code, l.nativeName])).toEqual([
      ["en", "English"],
      ["fr", "Français"],
    ]);
  });
});

describe("storage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("treats storage that throws as empty", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("blocked");
        },
        setItem: () => {
          throw new Error("blocked");
        },
      },
    });
    expect(readStoredLanguage()).toBeNull();
  });

  it("remembers a choice and still switches when storage refuses it", async () => {
    const saved = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => saved.get(key) ?? null,
        setItem: (key: string, value: string) => void saved.set(key, value),
      },
    });
    const change = vi.spyOn(i18n, "changeLanguage").mockResolvedValue(i18n.t);
    await setLanguage("fr");
    expect(saved.get(LANGUAGE_STORAGE_KEY)).toBe("fr");
    expect(change).toHaveBeenCalledWith("fr");

    vi.stubGlobal("window", {
      localStorage: {
        setItem: () => {
          throw new Error("blocked");
        },
      },
    });
    await setLanguage("en");
    expect(change).toHaveBeenLastCalledWith("en");

    await setLanguage("de");
    expect(change).toHaveBeenCalledTimes(2);
    change.mockRestore();
  });
});

describe("currentLocale", () => {
  it("is the app language", () => {
    expect(currentLocale()).toBe("en");
  });
});
