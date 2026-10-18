import { Check, ChevronDown, Globe } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { countryName, filterCountries, isCountryCode, sortedCountries } from "@/lib/countries";
import { cn } from "@/lib/utils";

interface CountryPickerProps {
  /** Given to the trigger, so a `Label`'s `htmlFor` points at it. */
  id?: string;
  /** An ISO 3166-1 alpha-2 code, or whatever two letters are stored, or "". */
  value: string;
  onChange: (code: string) => void;
  disabled?: boolean;
  invalid?: boolean;
}

function Flag({ code, size }: { code: string; size: number }) {
  // The name is always printed beside the flag, so the image itself is decorative.
  return (
    <img
      src={`/flags/${code.toLowerCase()}.svg`}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      className="shrink-0 rounded-full"
    />
  );
}

/**
 * A country field: a searchable list of every ISO 3166-1 country with its flag and its name
 * in the interface language, storing the two-letter code. Looks like the app's `Select`
 * when closed. A stored code that is not an ISO country (old data, such as "ZZ") is shown as
 * is with a globe instead of a flag and is never rewritten: it stays until a country is
 * picked.
 */
export function CountryPicker({ id, value, onChange, disabled, invalid }: CountryPickerProps) {
  const { t, i18n } = useTranslation(["common"]);
  const language = i18n.resolvedLanguage ?? "en";
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const countries = useMemo(() => sortedCountries(language), [language]);
  const matches = useMemo(() => filterCountries(countries, query), [countries, query]);
  const known = isCountryCode(value);

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) setQuery("");
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          id={id}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid}
          disabled={disabled}
          className="border-input bg-background focus:ring-ring flex h-10 w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm focus:ring-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="flex min-w-0 items-center gap-2 text-left">
            {!value ? (
              <span className="text-muted-foreground truncate">{t("Select a country…")}</span>
            ) : known ? (
              <>
                <Flag code={value} size={16} />
                <span className="truncate">{countryName(value, language)}</span>
              </>
            ) : (
              <>
                <Globe className="h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
                <span>{value}</span>
              </>
            )}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-trigger-width)] min-w-64 p-0"
      >
        {/* Filtered here rather than by cmdk: its fuzzy score would also rank any name with
            the query's letters scattered through it. */}
        <Command shouldFilter={false}>
          <CommandInput
            placeholder={t("Search countries…")}
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            <CommandEmpty>{t("No country found.")}</CommandEmpty>
            <CommandGroup>
              {matches.map((country) => (
                <CommandItem
                  key={country.code}
                  value={country.code}
                  onSelect={() => {
                    onChange(country.code);
                    handleOpenChange(false);
                  }}
                >
                  <Flag code={country.code} size={20} />
                  <span className="truncate">{country.name}</span>
                  <span className="text-muted-foreground ml-auto pl-2 text-xs">
                    {country.code}
                  </span>
                  <Check
                    className={cn(
                      "h-4 w-4 shrink-0",
                      country.code === value ? "opacity-100" : "opacity-0",
                    )}
                    aria-hidden="true"
                  />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
