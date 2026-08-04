import i18n from "i18next";
import HttpBackend from "i18next-http-backend";
import { initReactI18next } from "react-i18next";

// Namespaces mirror the requirement docs' feature epics (see
// docs/architecture/frontend.md#internationalization-i18n) plus `common` for
// generic, reused-everywhere strings (actions, statuses, nav chrome).
export const NAMESPACES = [
  "common",
  "auth",
  "home",
  "timesheet",
  "projects",
  "company",
  "user",
] as const;

void i18n
  .use(HttpBackend)
  .use(initReactI18next)
  .init({
    // English only for now (see docs/requirements/home.md#appearance) — components
    // are still written translation-ready via t(), so adding a language later is
    // just new JSON files under public/locales, not a component rewrite.
    lng: "en",
    fallbackLng: "en",
    ns: NAMESPACES,
    defaultNS: "common",
    backend: {
      loadPath: "/locales/{{lng}}/{{ns}}.json",
    },
    interpolation: {
      escapeValue: false, // React already escapes rendered output
    },
    react: {
      useSuspense: true,
    },
  });

export default i18n;
