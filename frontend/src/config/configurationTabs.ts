export interface ConfigurationTab {
  /** Path segment under /configuration, also the tab's value. */
  value: string;
  /** English source string, used as the common-namespace translation key. */
  label: string;
}

export const CONFIGURATION_TABS: ConfigurationTab[] = [
  { value: "general", label: "General" },
  { value: "companies", label: "Companies" },
  { value: "users", label: "Users" },
];

/**
 * The tab a /configuration/... path belongs to, by its first segment after
 * /configuration, so nested screens (a company's form, the new-user form) keep their
 * section's tab active. Undefined for paths that match no tab.
 */
export function configurationTabForPath(pathname: string): string | undefined {
  const segment = pathname.split("/")[2];
  return CONFIGURATION_TABS.find((tab) => tab.value === segment)?.value;
}
