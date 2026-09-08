import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { listUsers } from "@/api/users";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { ProjectManager } from "@/types/project";
import type { User } from "@/types/user";

// Matches the Service Line Consultants picker's debounce (see
// ServiceLineFormDialog.tsx) — same rationale, applied to this search instead.
const SEARCH_DEBOUNCE_MS = 300;

interface ProjectManagersPickerProps {
  selected: ProjectManager[];
  onChange: (next: ProjectManager[]) => void;
  disabled?: boolean;
}

// Same design language as the Service Line Consultants picker — a Popover+Command
// palette with server-side search and removable chips — but persisted differently:
// this is a field on the Project itself, submitted with the rest of the Project
// Form's fields on its own Save, not through a child-entity modal with its own
// immediate save.
export function ProjectManagersPicker({
  selected,
  onChange,
  disabled,
}: ProjectManagersPickerProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<User[]>([]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const handle = setTimeout(
      () => {
        listUsers({ role: "project_manager", search: search || undefined, is_active: true })
          .then((response) => {
            if (!cancelled) setResults(response.items);
          })
          .catch(() => {
            if (!cancelled) setResults([]);
          });
      },
      search ? SEARCH_DEBOUNCE_MS : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [open, search]);

  function toggle(manager: ProjectManager) {
    const isSelected = selected.some((m) => m.id === manager.id);
    onChange(
      isSelected ? selected.filter((m) => m.id !== manager.id) : [...selected, manager],
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button type="button" variant="outline" className="w-fit" disabled={disabled}>
            {t("Select Project Managers…")}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72 p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={t("Search project managers…")}
              value={search}
              onValueChange={setSearch}
            />
            <CommandList>
              <CommandEmpty>{t("No project managers found.")}</CommandEmpty>
              <CommandGroup>
                {results.map((manager) => {
                  const isSelected = selected.some((m) => m.id === manager.id);
                  return (
                    <CommandItem
                      key={manager.id}
                      value={manager.id}
                      onSelect={() => toggle(manager)}
                    >
                      <span className="flex h-4 w-4 items-center justify-center">
                        {isSelected && <Check className="h-4 w-4" aria-hidden="true" />}
                      </span>
                      {manager.full_name}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((manager) => (
            <Badge key={manager.id} variant="secondary" className="gap-1 pr-1">
              {manager.full_name}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => toggle(manager)}
                  className="rounded-full p-0.5 hover:bg-background"
                >
                  <X className="h-3 w-3" aria-hidden="true" />
                  <span className="sr-only">
                    {t("Remove {{name}}", { name: manager.full_name })}
                  </span>
                </button>
              )}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
