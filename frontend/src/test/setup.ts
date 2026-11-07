import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { afterEach, expect } from "vitest";

import auth from "../../public/locales/en/auth.json";
import common from "../../public/locales/en/common.json";
import company from "../../public/locales/en/company.json";
import configuration from "../../public/locales/en/configuration.json";
import invoices from "../../public/locales/en/invoices.json";
import projects from "../../public/locales/en/projects.json";
import timesheet from "../../public/locales/en/timesheet.json";
import user from "../../public/locales/en/user.json";
import authFr from "../../public/locales/fr/auth.json";
import commonFr from "../../public/locales/fr/common.json";
import companyFr from "../../public/locales/fr/company.json";
import configurationFr from "../../public/locales/fr/configuration.json";
import invoicesFr from "../../public/locales/fr/invoices.json";
import projectsFr from "../../public/locales/fr/projects.json";
import timesheetFr from "../../public/locales/fr/timesheet.json";
import userFr from "../../public/locales/fr/user.json";

// Global i18next instance for tests that render components calling useTranslation() with no
// I18nextProvider around them; without it react-i18next warns on every such test and quietly
// returns the key. It is loaded with the same English JSON the app ships, so a key used by a
// component but absent from the files fails the test that rendered it. Tests that build their
// own instance and wrap their markup in I18nextProvider are unaffected: the provider wins.
// French is loaded too, so a test that switches the language renders real French text.
//
// Deliberately not "@/i18n": that module registers the HTTP backend, which would try to fetch
// /locales/... during a test run.
const missing: string[] = [];

void i18n.use(initReactI18next).init({
  lng: "en",
  resources: {
    en: { auth, common, company, configuration, invoices, projects, timesheet, user },
    fr: {
      auth: authFr,
      common: commonFr,
      company: companyFr,
      configuration: configurationFr,
      invoices: invoicesFr,
      projects: projectsFr,
      timesheet: timesheetFr,
      user: userFr,
    },
  },
  defaultNS: "common",
  // Synchronous init with the namespaces preloaded, so nothing suspends while rendering.
  initAsync: false,
  saveMissing: true,
  missingKeyHandler: (_lngs, ns, key) => {
    missing.push(`${ns}:${key}`);
  },
  interpolation: { escapeValue: false },
});

afterEach(async () => {
  // A test that switched language must not leak it into the next one.
  if (i18n.language !== "en") await i18n.changeLanguage("en");
  const keys = missing.splice(0);
  expect(keys, "translation keys missing from public/locales").toEqual([]);
});
