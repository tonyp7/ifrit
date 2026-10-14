import { describe, expect, it } from "vitest";

import {
  COUNTRY_CODES,
  countryName,
  filterCountries,
  isCountryCode,
  sortedCountries,
} from "@/lib/countries";

describe("COUNTRY_CODES", () => {
  it("holds the 249 assigned ISO 3166-1 alpha-2 codes, upper case and unique", () => {
    expect(COUNTRY_CODES).toHaveLength(249);
    expect(new Set(COUNTRY_CODES).size).toBe(249);
    expect(COUNTRY_CODES.every((code) => /^[A-Z]{2}$/.test(code))).toBe(true);
  });

  it("has exactly one flag file per code, and no other flag", () => {
    // nginx answers a missing file with index.html, so a missing flag would not 404: it
    // would silently be a broken image. Keep the folder and the list in step.
    // import.meta.glob lists the matching files at build time; lazy, so nothing is loaded.
    const files = Object.keys(import.meta.glob("../../public/flags/*.svg")).map((path) =>
      path.slice(path.lastIndexOf("/") + 1),
    );
    const expected = COUNTRY_CODES.map((code) => `${code.toLowerCase()}.svg`);
    expect([...files].sort()).toEqual([...expected].sort());
  });
});

describe("isCountryCode", () => {
  it("accepts ISO codes only", () => {
    expect(isCountryCode("BE")).toBe(true);
    expect(isCountryCode("UK")).toBe(false);
    expect(isCountryCode("ZZ")).toBe(false);
    expect(isCountryCode("XK")).toBe(false);
    expect(isCountryCode("be")).toBe(false);
  });
});

describe("countryName", () => {
  it("names a country in the given language", () => {
    expect(countryName("BE", "en")).toBe("Belgium");
    expect(countryName("SG", "en")).toBe("Singapore");
  });
});

describe("filterCountries", () => {
  const countries = sortedCountries("en");
  const codes = (query: string) => filterCountries(countries, query).map((c) => c.code);

  it("returns every country, in name order, for an empty query", () => {
    expect(codes("  ")).toHaveLength(249);
    const names = filterCountries(countries, "").map((c) => c.name);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, "en")));
  });

  it("matches part of a name, ignoring case", () => {
    expect(codes("belg")).toEqual(["BE"]);
    expect(codes("SING")).toEqual(["SG"]);
  });

  it("puts an exact code match first", () => {
    expect(codes("gb")[0]).toBe("GB");
  });

  it("ignores accents", () => {
    expect(codes("cote")).toContain("CI");
  });
});
