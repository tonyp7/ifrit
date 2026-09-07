import { useTranslation } from "react-i18next";

import { AddServiceLineSelect } from "@/components/timesheet/AddServiceLineSelect";
import { LockServiceLineControl } from "@/components/timesheet/LockServiceLineControl";
import { RemoveServiceLineControl } from "@/components/timesheet/RemoveServiceLineControl";
import { serviceLineBorderColor } from "@/lib/timesheetColors";
import {
  formatWeekdayNarrow,
  formatWeekdayShort,
  isToday,
  isWeekend,
  toDayKey,
} from "@/lib/timesheetDates";
import { cellKey, formatHours } from "@/lib/timesheetHours";
import { cn } from "@/lib/utils";
import type {
  EligibleServiceLine,
  EntryCell,
  PeriodType,
  ServiceLineRow,
} from "@/types/timesheet";

interface TimesheetDesktopGridProps {
  periodType: PeriodType;
  days: Date[];
  serviceLines: ServiceLineRow[];
  entries: Record<string, EntryCell>;
  dayTotal: (dayKey: string) => number;
  serviceLineTotal: (serviceLineId: string) => number;
  periodTotal: number;
  periodLabel: string;
  addOptions: EligibleServiceLine[];
  onAddServiceLine: (serviceLineId: string) => void;
  hasEntriesInPeriod: (serviceLineId: string) => boolean;
  hasLockedEntriesInPeriod: (serviceLineId: string) => boolean;
  /** The entry owner is no longer currently assigned to this service line — see
   * specs/requirements/timesheet.md#persistence: read-only regardless of lock. */
  isUnassignedInPeriod: (serviceLineId: string) => boolean;
  onRemoveServiceLine: (serviceLineId: string) => void;
  onClearAndRemoveServiceLine: (serviceLineId: string) => Promise<void>;
  onCellChange: (serviceLineId: string, dayKey: string, value: string) => void;
  onCellBlur: (serviceLineId: string, dayKey: string) => void;
  // Keeps `selectedKey` pointed at whatever day the user is actually looking at on
  // desktop, so a later Week<->Month switch re-anchors on that day instead of a
  // stale value — see specs/requirements/timesheet.md#shared-header-all-breakpoints.
  onFocusDay: (dayKey: string) => void;
  /** Validation screen only — see specs/requirements/timesheet.md's Validation §
   * Lock / Unlock. Left undefined on My Timesheet, which has no lock control. */
  isFullyLockedInPeriod?: (serviceLineId: string) => boolean;
  onToggleLock?: (serviceLineId: string) => Promise<void>;
}

export function TimesheetDesktopGrid({
  periodType,
  days,
  serviceLines,
  entries,
  dayTotal,
  serviceLineTotal,
  periodTotal,
  periodLabel,
  addOptions,
  onAddServiceLine,
  hasEntriesInPeriod,
  hasLockedEntriesInPeriod,
  isUnassignedInPeriod,
  onRemoveServiceLine,
  onClearAndRemoveServiceLine,
  onCellChange,
  onCellBlur,
  onFocusDay,
  isFullyLockedInPeriod,
  onToggleLock,
}: TimesheetDesktopGridProps) {
  const { t } = useTranslation(["timesheet"]);

  // Month view crams up to 31 day columns into the same viewport Week view only
  // needs 7 for — at Week view's widths that overflows a maximized 1080p window
  // by ~500px. Shrinking column floors only for Month (Week keeps its wider,
  // more comfortable sizing) closes that gap; overflow-x-auto below stays as a
  // fallback for anyone on a narrower window. See the design discussion in
  // conversation before this change for the actual pixel math.
  const isMonth = periodType === "month";
  const dayColWidth = isMonth ? "min-w-12" : "min-w-16";
  const firstColWidth = isMonth ? "min-w-48" : "min-w-56";
  const lastColWidth = isMonth ? "min-w-16" : "min-w-20";

  return (
    <div className="hidden flex-col gap-4 p-4 md:flex">
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th
                className={cn(
                  "sticky left-0 top-0 z-30 border-b border-r bg-background p-2 text-left",
                  firstColWidth,
                )}
              >
                {t("Service line")}
              </th>
              {days.map((day) => {
                const dayKey = toDayKey(day);
                return (
                  <th
                    key={dayKey}
                    className={cn(
                      "sticky top-0 z-20 border-b p-2 text-center font-medium",
                      dayColWidth,
                      isWeekend(day) && "bg-muted/40",
                      !isWeekend(day) && "bg-background",
                      isToday(day) && "border-t-2 border-t-primary",
                    )}
                  >
                    <div className="text-xs text-muted-foreground">
                      {periodType === "week"
                        ? formatWeekdayShort(day)
                        : formatWeekdayNarrow(day)}
                    </div>
                    <div>{day.getDate()}</div>
                  </th>
                );
              })}
              <th
                className={cn(
                  "sticky right-0 top-0 z-30 border-b border-l bg-background p-2 text-right",
                  lastColWidth,
                )}
              >
                {t("Total")}
              </th>
            </tr>
          </thead>
          <tbody>
            {serviceLines.map((line, index) => (
              <tr key={line.service_line_id}>
                <td
                  className={cn(
                    "sticky left-0 z-10 border-b border-r border-l-4 bg-background p-2",
                    firstColWidth,
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
                    {isFullyLockedInPeriod && onToggleLock && (
                      <LockServiceLineControl
                        isFullyLocked={isFullyLockedInPeriod(line.service_line_id)}
                        onToggle={() => onToggleLock(line.service_line_id)}
                      />
                    )}
                    <RemoveServiceLineControl
                      hasEntries={hasEntriesInPeriod(line.service_line_id)}
                      hasLockedEntries={hasLockedEntriesInPeriod(line.service_line_id)}
                      isUnassigned={isUnassignedInPeriod(line.service_line_id)}
                      periodLabel={periodLabel}
                      onRemove={() => onRemoveServiceLine(line.service_line_id)}
                      onConfirmedClear={() =>
                        onClearAndRemoveServiceLine(line.service_line_id)
                      }
                    />
                  </div>
                </td>
                {days.map((day) => {
                  const dayKey = toDayKey(day);
                  const key = cellKey(line.service_line_id, dayKey);
                  const cell = entries[key];
                  const locked = cell?.is_locked ?? false;
                  const unassigned = !locked && isUnassignedInPeriod(line.service_line_id);
                  const weekend = isWeekend(day);
                  // Resolved to a single class, not left as several `cn()` entries that
                  // could combine — `cn()`/`tailwind-merge` treats same-property
                  // background-color utilities as conflicting and silently drops all but
                  // the last one, so e.g. `isWeekend && "bg-muted/40"` plus
                  // `locked && "bg-red-100"` on the same weekend+locked cell would only
                  // ever render the red, losing the weekend shading entirely. Each branch
                  // here already bakes the weekend variant in, so there's nothing left to
                  // merge/collide. Locked still wins over unassigned if both apply — see
                  // specs/requirements/timesheet.md's Validation § Lock / Unlock.
                  const backgroundClass = locked
                    ? weekend
                      ? "bg-red-200 dark:bg-red-900/50"
                      : "bg-red-100 dark:bg-red-950/40"
                    : unassigned
                      ? weekend
                        ? "bg-muted/80"
                        : "bg-muted/60"
                      : weekend
                        ? "bg-muted/40"
                        : undefined;
                  return (
                    <td
                      key={dayKey}
                      className={cn("border-b p-1 text-center", backgroundClass)}
                    >
                      <input
                        type="number"
                        step={0.5}
                        min={0}
                        max={24}
                        inputMode="decimal"
                        disabled={locked || unassigned}
                        title={
                          unassigned
                            ? t(
                                "This consultant is no longer assigned to this service line — read-only.",
                              )
                            : undefined
                        }
                        value={cell?.hours ?? ""}
                        onChange={(e) =>
                          onCellChange(line.service_line_id, dayKey, e.target.value)
                        }
                        onBlur={() => onCellBlur(line.service_line_id, dayKey)}
                        onFocus={() => onFocusDay(dayKey)}
                        aria-label={t("Hours")}
                        className={cn(
                          "w-full rounded border border-transparent bg-transparent p-1 text-center text-sm outline-none transition-colors",
                          // At-rest + hover affordance for editable cells only (see
                          // conversation before this change) — reuses this project's
                          // own tokens: bg-muted is already used for weekend shading
                          // in this same grid, hover:bg-secondary/50 is the exact
                          // convention TableRow (ui/table.tsx) already uses elsewhere.
                          // `enabled:` scopes both so a locked cell stays visually
                          // flat, distinguishing editable from locked at a glance.
                          "enabled:bg-muted/20 enabled:hover:bg-secondary/50",
                          // `!` (important) here isn't decorative — without it, focus
                          // loses to the enabled:* rules above on equal specificity
                          // (Tailwind sorts `enabled:` after `focus:` in its generated
                          // cascade), so a focused cell would silently keep showing
                          // the at-rest/hover tint instead of the intended solid
                          // focus background. Confirmed via computed styles before
                          // adding this.
                          "focus:!border-input focus:!bg-background",
                          // Matches ui/input.tsx's own disabled convention
                          // (cursor-not-allowed + opacity-50) rather than a
                          // one-off treatment.
                          "disabled:cursor-not-allowed disabled:opacity-50",
                          "[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
                        )}
                      />
                    </td>
                  );
                })}
                <td
                  className={cn(
                    "sticky right-0 z-10 border-b border-l bg-background p-2 text-right font-medium",
                    lastColWidth,
                  )}
                >
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
