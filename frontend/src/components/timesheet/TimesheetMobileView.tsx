import { useTranslation } from "react-i18next";

import { AddServiceLineSelect } from "@/components/timesheet/AddServiceLineSelect";
import { RemoveServiceLineControl } from "@/components/timesheet/RemoveServiceLineControl";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { serviceLineBorderColor } from "@/lib/timesheetColors";
import { formatFullDate, formatWeekdayShort, isToday, toDayKey } from "@/lib/timesheetDates";
import { cellKey, formatHours } from "@/lib/timesheetHours";
import type { EligibleServiceLine, EntryCell, ServiceLineRow } from "@/types/timesheet";

interface TimesheetMobileViewProps {
  days: Date[];
  selectedKey: string;
  onSelectDay: (dayKey: string) => void;
  serviceLines: ServiceLineRow[];
  entries: Record<string, EntryCell>;
  dayTotal: (dayKey: string) => number;
  monthToDateTotal: number;
  periodLabel: string;
  addOptions: EligibleServiceLine[];
  onAddServiceLine: (serviceLineId: string) => void;
  hasEntriesInPeriod: (serviceLineId: string) => boolean;
  hasLockedEntriesInPeriod: (serviceLineId: string) => boolean;
  onRemoveServiceLine: (serviceLineId: string) => void;
  onClearAndRemoveServiceLine: (serviceLineId: string) => Promise<void>;
  onCellChange: (serviceLineId: string, dayKey: string, value: string) => void;
  onCellBlur: (serviceLineId: string, dayKey: string) => void;
}

export function TimesheetMobileView({
  days,
  selectedKey,
  onSelectDay,
  serviceLines,
  entries,
  dayTotal,
  monthToDateTotal,
  periodLabel,
  addOptions,
  onAddServiceLine,
  hasEntriesInPeriod,
  hasLockedEntriesInPeriod,
  onRemoveServiceLine,
  onClearAndRemoveServiceLine,
  onCellChange,
  onCellBlur,
}: TimesheetMobileViewProps) {
  const { t } = useTranslation(["timesheet"]);
  const selectedDate = days.find((d) => toDayKey(d) === selectedKey) ?? days[0];

  return (
    <div className="flex flex-col md:hidden">
      <div className="flex gap-2 overflow-x-auto border-b p-3">
        {days.map((day) => {
          const dayKey = toDayKey(day);
          const selected = dayKey === selectedKey;
          const total = dayTotal(dayKey);
          return (
            <button
              key={dayKey}
              type="button"
              onClick={() => onSelectDay(dayKey)}
              className={cn(
                "flex shrink-0 flex-col items-center gap-0.5 rounded-md border px-3 py-2 text-xs",
                selected
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input bg-background",
              )}
            >
              <span className="relative font-medium">
                {formatWeekdayShort(day)}
                {isToday(day) && (
                  <span
                    className={cn(
                      "absolute -right-1.5 -top-1 h-1.5 w-1.5 rounded-full",
                      selected ? "bg-primary-foreground" : "bg-primary",
                    )}
                  />
                )}
              </span>
              <span className="text-sm font-semibold">{day.getDate()}</span>
              <span className="opacity-80">{formatHours(total) || "0"}h</span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-4 p-4 pb-24">
        <div className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold">{formatFullDate(selectedDate)}</h2>
          <span className="text-sm font-medium">
            {formatHours(dayTotal(selectedKey)) || "0"}h
          </span>
        </div>

        {serviceLines.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t("No service lines added yet. Use “Add service line” below to start logging time.")}
          </p>
        )}

        <div className="flex flex-col gap-2">
          {serviceLines.map((line, index) => {
            const key = cellKey(line.service_line_id, selectedKey);
            const cell = entries[key];
            const locked = cell?.is_locked ?? false;
            return (
              <div
                key={line.service_line_id}
                className={cn(
                  "flex items-center gap-3 rounded-md border-l-4 bg-card p-3",
                  serviceLineBorderColor(index),
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{line.project_name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {line.service_line_name ?? t("(unnamed service line)")}
                  </p>
                </div>
                <Input
                  type="number"
                  step={0.5}
                  min={0}
                  max={24}
                  inputMode="decimal"
                  disabled={locked}
                  value={cell?.hours ?? ""}
                  onChange={(e) =>
                    onCellChange(line.service_line_id, selectedKey, e.target.value)
                  }
                  onBlur={() => onCellBlur(line.service_line_id, selectedKey)}
                  className="w-20 text-right"
                  aria-label={t("Hours")}
                />
                <RemoveServiceLineControl
                  hasEntries={hasEntriesInPeriod(line.service_line_id)}
                  hasLockedEntries={hasLockedEntriesInPeriod(line.service_line_id)}
                  periodLabel={periodLabel}
                  onRemove={() => onRemoveServiceLine(line.service_line_id)}
                  onConfirmedClear={() =>
                    onClearAndRemoveServiceLine(line.service_line_id)
                  }
                />
              </div>
            );
          })}
        </div>

        <AddServiceLineSelect options={addOptions} onAdd={onAddServiceLine} />
      </div>

      <div className="fixed inset-x-0 bottom-14 flex items-center justify-between border-t bg-background/95 p-3 text-sm backdrop-blur">
        <span>
          {t("Today")}: <strong>{formatHours(dayTotal(selectedKey)) || "0"}h</strong>
        </span>
        <span>
          {t("Month to date")}: <strong>{formatHours(monthToDateTotal) || "0"}h</strong>
        </span>
      </div>
    </div>
  );
}
