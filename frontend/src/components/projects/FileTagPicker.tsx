import { Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { FileTag } from "@/types/file";

interface FileTagPickerProps {
  /** Tags the file does not have yet. */
  available: FileTag[];
  disabled?: boolean;
  onSelect: (tag: FileTag) => void;
}

/**
 * The "+ Tag" button and its searchable list. Choosing a tag does not touch the popover's
 * open state, so several tags can be added in one go; Enter chooses the highlighted tag
 * and Escape closes the popover (Radix and cmdk do both).
 */
export function FileTagPicker({ available, disabled, onSelect }: FileTagPickerProps) {
  const { t } = useTranslation(["projects"]);
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={disabled}
          aria-label={t("Add tag")}
          className="h-6 gap-1 rounded-full px-2 text-xs"
        >
          <Plus className="h-3 w-3" aria-hidden="true" />
          {t("Tag")}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-0">
        <Command>
          <CommandInput placeholder={t("Search tags…")} />
          <CommandList>
            <CommandEmpty>{t("No matching tags.")}</CommandEmpty>
            {available.map((tag) => (
              <CommandItem key={tag.id} value={tag.name} onSelect={() => onSelect(tag)}>
                {tag.name}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
