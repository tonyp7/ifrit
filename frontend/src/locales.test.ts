import { describe, expect, it } from "vitest";

// Every language under public/locales must carry exactly the keys English does, with the same
// {{placeholders}}, or a screen silently falls back to English (or shows a bare key).
const PLURAL_SUFFIX = /^(.*)_(zero|one|two|few|many|other)$/;

type Messages = Record<string, string>;

// Read through Vite's glob import (it needs no Node types): language -> namespace -> messages.
const files = import.meta.glob<Messages>("../public/locales/*/*.json", {
  eager: true,
  import: "default",
});
const catalog: Record<string, Record<string, Messages>> = {};
for (const [path, messages] of Object.entries(files)) {
  const [, language, file] = /locales\/([^/]+)\/([^/]+)\.json$/.exec(path) ?? [];
  (catalog[language] ??= {})[file] = messages;
}

function load(language: string, namespace: string): Messages {
  return catalog[language][namespace];
}

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{\{\s*([\w.]+)\s*\}\}/g)].map((m) => m[1]).sort();
}

/** The keys a language must have: each plain key once, each plural base once per plural
 * category the language uses (French has `many` besides `one` and `other`, English does not). */
function expectedKeys(english: Messages, language: string): string[] {
  const categories = new Intl.PluralRules(language).resolvedOptions().pluralCategories;
  const keys = new Set<string>();
  for (const key of Object.keys(english)) {
    const plural = PLURAL_SUFFIX.exec(key);
    if (plural) for (const category of categories) keys.add(`${plural[1]}_${category}`);
    else keys.add(key);
  }
  return [...keys].sort();
}

const english = Object.keys(catalog.en);
const others = Object.keys(catalog).filter((language) => language !== "en");

describe("translation files", () => {
  it("has a French folder", () => {
    expect(others).toContain("fr");
  });

  for (const language of others) {
    for (const namespace of english) {
      describe(`${language}/${namespace}`, () => {
        const en = load("en", namespace);
        const other = load(language, namespace);

        it("has the same keys as English, plural forms included", () => {
          expect(Object.keys(other).sort()).toEqual(expectedKeys(en, language));
        });

        it("keeps every {{placeholder}} of the English text", () => {
          for (const [key, text] of Object.entries(other)) {
            const plural = PLURAL_SUFFIX.exec(key);
            // A plural form is checked against English's `other` form, which every English
            // plural has; plain keys against themselves.
            const source = plural ? en[`${plural[1]}_other`] : en[key];
            expect(placeholders(text), key).toEqual(placeholders(source));
          }
        });

        it("has no empty text", () => {
          for (const [key, text] of Object.entries(other)) {
            expect(text.trim(), key).not.toBe("");
          }
        });
      });
    }
  }

  it("has no key with a bare colon, which i18next would read as a namespace", () => {
    for (const namespace of english) {
      for (const key of Object.keys(load("en", namespace))) {
        expect(key, `${namespace}: ${key}`).not.toMatch(/:(?!\s|$)/);
      }
    }
  });
});
