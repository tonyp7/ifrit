import { CalendarIcon } from "lucide-react";
import { useState } from "react";
import type { DateRange as PickerRange } from "react-day-picker";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useServiceLineLabel } from "@/hooks/useServiceLineLabel";
import {
  formatPeriod,
  PERIOD_PRESET_LABELS,
  PERIOD_PRESETS,
  presetRange,
  type PeriodPreset,
} from "@/lib/invoicePeriods";
import { parseDayKey, toDayKey } from "@/lib/timesheetDates";
import { cn } from "@/lib/utils";
import type { ContextServiceLine } from "@/types/invoice";

export interface Period {
  preset: PeriodPreset | null;
  start: string | null;
  end: string | null;
}

interface TmBillingPanelProps {
  serviceLines: ContextServiceLine[];
  selected: string[];
  onSelectedChange: (ids: string[]) => void;
  period: Period;
  onPeriodChange: (period: Period) => void;
  minorUnit: number | null;
  today: Date;
  disabled?: boolean;
}

/** What to bill on a Time & Material or Capped T&M project: the service lines and the
 * period whose hours are summed. */
export function TmBillingPanel({
  serviceLines,
  selected,
  onSelectedChange,
  period,
  onPeriodChange,
  minorUnit,
  today,
  disabled,
}: TmBillingPanelProps) {
  const { t } = useTranslation(["invoices"]);
  const label = useServiceLineLabel(minorUnit);
  const [pickerOpen, setPickerOpen] = useState(false);

  function toggle(id: string, checked: boolean) {
    onSelectedChange(
      checked ? [...selected, id] : selected.filter((selectedId) => selectedId !== id),
    );
  }

  function applyPreset(preset: PeriodPreset) {
    const range = presetRange(preset, today);
    onPeriodChange({ preset, start: toDayKey(range.start), end: toDayKey(range.end) });
  }

  // Editing the range by hand clears the preset label: the range no longer is one.
  function applyRange(range: PickerRange | undefined) {
    onPeriodChange({
      preset: null,
      start: range?.from ? toDayKey(range.from) : null,
      end: range?.to ? toDayKey(range.to) : range?.from ? toDayKey(range.from) : null,
    });
  }

  const pickerValue: PickerRange | undefined = period.start
    ? { from: parseDayKey(period.start), to: period.end ? parseDayKey(period.end) : undefined }
    : undefined;

  return (
    <div className="flex flex-col gap-4">
      <fieldset className="flex flex-col gap-2" disabled={disabled}>
        <legend className="mb-2 text-sm font-medium">{t("Service lines")}</legend>
        {serviceLines.length === 0 && (
          <p className="text-muted-foreground text-sm">
            {t("This project has no service lines.")}
          </p>
        )}
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-x-6">
          {serviceLines.map((line) => (
            <div key={line.id} className="flex items-center gap-2">
              <Checkbox
                id={`service_line_${line.id}`}
                checked={selected.includes(line.id)}
                disabled={disabled}
                onCheckedChange={(checked) => toggle(line.id, checked === true)}
              />
              <Label htmlFor={`service_line_${line.id}`} className="font-normal">
                {label(line)}
              </Label>
            </div>
          ))}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-2" disabled={disabled}>
        <legend className="mb-2 text-sm font-medium">{t("Period")}</legend>
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("Period presets")}>
          {PERIOD_PRESETS.map((preset) => (
            <Button
              key={preset}
              type="button"
              size="sm"
              variant={period.preset === preset ? "default" : "outline"}
              aria-pressed={period.preset === preset}
              disabled={disabled}
              onClick={() => applyPreset(preset)}
            >
              {t(PERIOD_PRESET_LABELS[preset])}
            </Button>
          ))}
        </div>
        <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
          <PopoverTrigger asChild>
            <Button
              id="period_range"
              type="button"
              variant="outline"
              disabled={disabled}
              className={cn(
                "w-full justify-start font-normal sm:w-80",
                !period.start && "text-muted-foreground",
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" aria-hidden="true" />
              {period.start && period.end
                ? formatPeriod(parseDayKey(period.start), parseDayKey(period.end))
                : t("Pick a period")}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="range"
              selected={pickerValue}
              defaultMonth={pickerValue?.from}
              // Weeks start on Monday, like the timesheet and the week presets.
              weekStartsOn={1}
              numberOfMonths={1}
              onSelect={applyRange}
            />
          </PopoverContent>
        </Popover>
      </fieldset>
    </div>
  );
}
