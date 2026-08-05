import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { AddServiceLineSelect } from "@/components/timesheet/AddServiceLineSelect";
import { Button } from "@/components/ui/button";
import { serviceLineBorderColor } from "@/lib/timesheetColors";
import { isToday, isWeekend, toDayKey } from "@/lib/timesheetDates";
import { cellKey, formatHours } from "@/lib/timesheetHours";
import { cn } from "@/lib/utils";
import type { EligibleServiceLine, EntryCell, ServiceLineRow } from "@/types/timesheet";

interface TimesheetDesktopGridProps {
  days: Date[];
  serviceLines: ServiceLineRow[];
  entries: Record<string, EntryCell>;
  dayTotal: (dayKey: string) => number;
  serviceLineTotal: (serviceLineId: string) => number;
  periodTotal: number;
  addOptions: EligibleServiceLine[];
  onAddServiceLine: (serviceLineId: string) => void;
  onRemoveServiceLine: (serviceLineId: string) => void;
  onCellChange: (serviceLineId: string, dayKey: string, value: string) => void;
  onCellBlur: (serviceLineId: string, dayKey: string) => void;
}

export function TimesheetDesktopGrid({
  days,
  serviceLines,
  entries,
  dayTotal,
  serviceLineTotal,
  periodTotal,
  addOptions,
  onAddServiceLine,
  onRemoveServiceLine,
  onCellChange,
  onCellBlur,
}: TimesheetDesktopGridProps) {
  const { t } = useTranslation(["timesheet"]);

  return (
    <div className="hidden flex-col gap-4 p-4 md:flex">
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 top-0 z-30 min-w-56 border-b border-r bg-background p-2 text-left">
                {t("Service line")}
              </th>
              {days.map((day) => {
                const dayKey = toDayKey(day);
                return (
                  <th
                    key={dayKey}
                    className={cn(
                      "sticky top-0 z-20 min-w-16 border-b p-2 text-center font-medium",
                      isWeekend(day) && "bg-muted/40",
                      !isWeekend(day) && "bg-background",
                      isToday(day) && "border-t-2 border-t-primary",
                    )}
                  >
                    <div className="text-xs text-muted-foreground">
                      {new Intl.DateTimeFormat(undefined, { weekday: "narrow" }).format(
                        day,
                      )}
                    </div>
                    <div>{day.getDate()}</div>
                  </th>
                );
              })}
              <th className="sticky right-0 top-0 z-30 min-w-20 border-b border-l bg-background p-2 text-right">
                {t("Total")}
              </th>
            </tr>
          </thead>
          <tbody>
            {serviceLines.map((line, index) => (
              <tr key={line.service_line_id}>
                <td
                  className={cn(
                    "sticky left-0 z-10 min-w-56 border-b border-r border-l-4 bg-background p-2",
                    serviceLineBorderColor(index),
                  )}
                >
                  <div className="flex items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{line.project_name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {line.service_line_name ?? t("(unnamed service line)")}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={t("Remove service line")}
                      onClick={() => onRemoveServiceLine(line.service_line_id)}
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </div>
                </td>
                {days.map((day) => {
                  const dayKey = toDayKey(day);
                  const key = cellKey(line.service_line_id, dayKey);
                  const cell = entries[key];
                  const locked = cell?.is_locked ?? false;
                  return (
                    <td
                      key={dayKey}
                      className={cn(
                        "border-b p-1 text-center",
                        isWeekend(day) && "bg-muted/40",
                      )}
                    >
                      <input
                        type="number"
                        step={0.5}
                        min={0}
                        max={24}
                        inputMode="decimal"
                        disabled={locked}
                        value={cell?.hours ?? ""}
                        onChange={(e) =>
                          onCellChange(line.service_line_id, dayKey, e.target.value)
                        }
                        onBlur={() => onCellBlur(line.service_line_id, dayKey)}
                        aria-label={t("Hours")}
                        className={cn(
                          "w-full rounded border border-transparent bg-transparent p-1 text-center text-sm outline-none",
                          "focus:border-input focus:bg-background",
                          "disabled:cursor-not-allowed disabled:text-muted-foreground",
                          "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
                        )}
                      />
                    </td>
                  );
                })}
                <td className="sticky right-0 z-10 border-b border-l bg-background p-2 text-right font-medium">
                  {formatHours(serviceLineTotal(line.service_line_id)) || "0"}h
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="sticky left-0 z-10 border-r bg-background p-2 font-semibold">
                {t("Total")}
              </td>
              {days.map((day) => {
                const dayKey = toDayKey(day);
                return (
                  <td
                    key={dayKey}
                    className={cn(
                      "p-2 text-center font-medium",
                      isWeekend(day) && "bg-muted/40",
                    )}
                  >
                    {formatHours(dayTotal(dayKey)) || "0"}
                  </td>
                );
              })}
              <td className="border-l bg-background p-2 text-right font-semibold">
                {formatHours(periodTotal) || "0"}h
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {serviceLines.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {t("No service lines added yet. Use “Add service line” below to start logging time.")}
        </p>
      )}

      <AddServiceLineSelect options={addOptions} onAdd={onAddServiceLine} />
    </div>
  );
}
