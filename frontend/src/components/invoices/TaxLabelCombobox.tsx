import { Check, ChevronsUpDown } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { TAX_PRESETS } from "@/lib/invoiceTaxes";
import { cn } from "@/lib/utils";

interface TaxLabelComboboxProps {
  value: string;
  /** `preset` is true when the label was picked from the list, not typed. */
  onChange: (label: string, preset: boolean) => void;
  invalid?: boolean;
  disabled?: boolean;
}

/** A tax name: one of the presets, or anything typed. What is typed is kept when the list
 * closes without a pick, so a custom name needs no extra step. */
export function TaxLabelCombobox({
  value,
  onChange,
  invalid,
  disabled,
}: TaxLabelComboboxProps) {
  const { t } = useTranslation(["invoices"]);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const typed = search.trim();

  function choose(label: string, preset: boolean) {
    onChange(label, preset);
    setSearch("");
    setOpen(false);
  }

  function handleOpenChange(next: boolean) {
    if (!next && typed && typed !== value) onChange(typed, false);
    setSearch(next ? value : "");
    setOpen(next);
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={t("Tax")}
          aria-invalid={invalid}
          disabled={disabled}
          className={cn(
            "w-full justify-between font-normal",
            !value && "text-muted-foreground",
          )}
        >
          <span className="truncate">{value || t("Choose or type…")}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-0">
        <Command>
          <CommandInput
            placeholder={t("Choose or type…")}
            value={search}
            onValueChange={setSearch}
            maxLength={100}
          />
          <CommandList>
            <CommandGroup>
              {typed && !TAX_PRESETS.some((preset) => preset === typed) && (
                <CommandItem value={`custom:${typed}`} onSelect={() => choose(typed, false)}>
                  {t("Use “{{label}}”", { label: typed })}
                </CommandItem>
              )}
              {TAX_PRESETS.map((preset) => (
                <CommandItem key={preset} value={preset} onSelect={() => choose(preset, true)}>
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      value === preset ? "opacity-100" : "opacity-0",
                    )}
                    aria-hidden="true"
                  />
                  {preset}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
