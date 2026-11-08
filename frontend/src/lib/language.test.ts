import i18n, { createInstance } from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applyDocumentLanguage,
  currentLocale,
  I18N_LANGUAGE_OPTIONS,
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

describe("Chinese", () => {
  it("starts in Simplified Chinese for every Simplified tag", () => {
    for (const tag of ["zh", "zh-CN", "zh-SG", "zh-Hans", "zh-Hans-SG", "ZH-cn", "zh_CN"]) {
      expect(resolveLanguage(null, [tag]), tag).toBe("zh-CN");
    }
  });

  it("does not match Traditional Chinese or another Chinese language", () => {
    for (const tag of ["zh-TW", "zh-HK", "zh-MO", "zh-Hant", "zh-Hant-TW", "yue-HK"]) {
      expect(resolveLanguage(null, [tag]), tag).toBe("en");
    }
  });

  it("moves on down the browser's list past Traditional Chinese", () => {
    expect(resolveLanguage(null, ["zh-TW", "fr-FR"])).toBe("fr");
    expect(resolveLanguage(null, ["zh-TW", "zh-CN"])).toBe("zh-CN");
    expect(resolveLanguage(null, ["zh-HK", "en-US", "zh-CN"])).toBe("en");
  });

  it("skips a tag that is not valid", () => {
    expect(resolveLanguage(null, ["not a tag!", "zh-CN"])).toBe("zh-CN");
    expect(resolveLanguage(null, ["", "_"])).toBe("en");
  });

  it("takes a stored choice only when it is exactly an offered code", () => {
    expect(resolveLanguage("zh-CN", ["fr"])).toBe("zh-CN");
    expect(resolveLanguage("ZH-cn", ["fr"])).toBe("zh-CN");
    expect(resolveLanguage("zh-TW", ["fr"])).toBe("fr");
    expect(resolveLanguage("zh", [])).toBe("en");
  });

  it("lets i18next load only offered languages, so no `zh` folder is requested", () => {
    const instance = createInstance();
    void instance.init({
      lng: "zh-CN",
      fallbackLng: "en",
      ...I18N_LANGUAGE_OPTIONS,
      initAsync: false,
      resources: {},
    });
    expect(instance.services.languageUtils.toResolveHierarchy("zh-CN")).toEqual([
      "zh-CN",
      "en",
    ]);
  });

  it("sets the page's lang attribute to the language in use", () => {
    const element = { lang: "en" };
    vi.stubGlobal("document", { documentElement: element });
    applyDocumentLanguage("zh-CN");
    expect(element.lang).toBe("zh-CN");
    vi.unstubAllGlobals();
  });
});

describe("offered languages", () => {
  it("names each language in itself", () => {
    expect(SUPPORTED_LANGUAGES.map((l) => [l.code, l.nativeName])).toEqual([
      ["en", "English"],
      ["fr", "Français"],
      ["zh-CN", "简体中文"],
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
