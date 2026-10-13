import { CalendarIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { dueDateFromSelection, formatDueDate } from "@/lib/billingMilestones";
import { parseDayKey } from "@/lib/timesheetDates";
import { cn } from "@/lib/utils";

interface DueDatePickerProps {
  id?: string;
  /** `YYYY-MM-DD`, or null for no date. */
  value: string | null;
  onChange: (value: string | null) => void;
}

/** An optional calendar date: shadcn's Date Picker recipe (a Popover holding a Calendar),
 * plus a Clear button, since the date can be removed again. */
export function DueDatePicker({ id, value, onChange }: DueDatePickerProps) {
  const { t } = useTranslation(["projects", "common"]);
  const [open, setOpen] = useState(false);
  const selected = value ? parseDayKey(value) : undefined;

  function select(next: string | null) {
    onChange(next);
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          className={cn("w-full justify-start font-normal", !value && "text-muted-foreground")}
        >
          <CalendarIcon className="mr-2 h-4 w-4" aria-hidden="true" />
          {value ? formatDueDate(value) : t("Pick a date")}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          defaultMonth={selected}
          // Weeks start on Monday, like the timesheet.
          weekStartsOn={1}
          onSelect={(date) => select(dueDateFromSelection(date))}
        />
        {value && (
          <div className="border-t p-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => select(null)}
            >
              {t("Clear date")}
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
