import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export interface ReportFilterOption {
  id: string;
  label: string;
}

interface ReportFilterDropdownProps {
  label: string;
  icon: LucideIcon;
  options: ReportFilterOption[];
  selected: string[];
  onChange: (next: string[]) => void;
  /** Project Status is exactly 3 fixed values — a search bar over 3 items is
   * pointless UI (see reporting.md), so this defaults to true but that one
   * dropdown passes false. */
  searchable?: boolean;
}

// One of the Reporting screen's four filter dropdowns — a Popover+Command palette
// like the Project Managers/Consultants pickers elsewhere in this app, but
// rendering an actual Checkbox per option (not just a check icon) and staying a
// pure filter (no removable chips below the trigger — the dropdown's own checked
// state already is the selection). Client-side search: unlike those other
// pickers, this screen's option lists are small, static, and fetched once
// up front (GET /time-entries/report/filters), so there's no server round trip
// per keystroke to debounce here.
export function ReportFilterDropdown({
  label,
  icon: Icon,
  options,
  selected,
  onChange,
  searchable = true,
}: ReportFilterDropdownProps) {
  const { t } = useTranslation(["timesheet"]);
  const [open, setOpen] = useState(false);

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" className="gap-2">
          <Icon className="h-4 w-4" aria-hidden="true" />
          {label}
          {selected.length > 0 && (
            <Badge variant="secondary" className="ml-1 px-1.5">
              {selected.length}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          {searchable && <CommandInput placeholder={t("Search…")} />}
          <CommandList>
            <CommandEmpty>{t("No results found.")}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => {
                const isSelected = selected.includes(option.id);
                return (
                  <CommandItem
                    key={option.id}
                    value={option.label}
                    onSelect={() => toggle(option.id)}
                    className="gap-2"
                  >
                    <Checkbox checked={isSelected} className="pointer-events-none" />
                    {option.label}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
