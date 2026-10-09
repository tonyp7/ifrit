import { useTranslation } from "react-i18next";

import { AddServiceLineSelect } from "@/components/timesheet/AddServiceLineSelect";
import { LockServiceLineControl } from "@/components/timesheet/LockServiceLineControl";
import { RemoveServiceLineControl } from "@/components/timesheet/RemoveServiceLineControl";
import { lockedCellClass, serviceLineBorderColor } from "@/lib/timesheetColors";
import {
  formatWeekdayNarrow,
  formatWeekdayShort,
  isToday,
  isWeekend,
  toDayKey,
} from "@/lib/timesheetDates";
import { cellKey, formatHours } from "@/lib/timesheetHours";
import { shouldShowAddLineHint } from "@/lib/timesheetServiceLines";
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
  // Every callback below that identifies "which row" takes a leading `userId`,
  // needed because Reporting's rows span many different consultants in one grid
  // instance, unlike My Timesheet (whose hook ignores it, already
  // knowing its own single owner), see useTimesheetGrid's own comment on this.
  serviceLineTotal: (userId: string, serviceLineId: string) => number;
  periodTotal: number;
  periodLabel: string;
  /** My Timesheet only: Reporting has no "Add service line" affordance
   * (its row set is entirely filter-driven), so these three are left undefined
   * there and the Add control simply isn't rendered. */
  addOptions?: EligibleServiceLine[];
  onAddServiceLine?: (serviceLineId: string) => void;
  /** My Timesheet only, alongside the above: Reporting has "no X icon
   * to delete a line" per its own spec, so these two (and the row's remove
   * control) are left undefined there too. */
  hasEntriesInPeriod?: (userId: string, serviceLineId: string) => boolean;
  hasLockedEntriesInPeriod?: (userId: string, serviceLineId: string) => boolean;
  onRemoveServiceLine?: (userId: string, serviceLineId: string) => void;
  onClearAndRemoveServiceLine?: (userId: string, serviceLineId: string) => Promise<void>;
  /** The entry owner is no longer currently assigned to this service line:
   * read-only regardless of lock. Still required on every screen, including
   * Reporting (driven there by each row's own `is_assigned`). */
  isUnassignedInPeriod: (userId: string, serviceLineId: string) => boolean;
  /** Reporting only: overrides the tooltip shown on an unassigned cell with a
   * reason specific to *why* (the project's still in Draft, or closed), rather
   * than always claiming the consultant was personally removed, which often
   * isn't the actual cause. My Timesheet leave this undefined and
   * keep the default generic message below. */
  unassignedTooltip?: (userId: string, serviceLineId: string) => string;
  onCellChange: (userId: string, serviceLineId: string, dayKey: string, value: string) => void;
  onCellFocus: (userId: string, serviceLineId: string, dayKey: string) => void;
  onCellBlur: (userId: string, serviceLineId: string, dayKey: string, badInput: boolean) => void;
  // Keeps `selectedKey` pointed at whatever day the user is actually looking at on
  // desktop, so a later Week<->Month switch re-anchors on that day instead of a
  // stale value.
  onFocusDay: (dayKey: string) => void;
  /** My Timesheet never sets these: no lock control there. */
  isFullyLockedInPeriod?: (userId: string, serviceLineId: string) => boolean;
  onToggleLock?: (userId: string, serviceLineId: string) => Promise<void>;
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
  unassignedTooltip,
  onRemoveServiceLine,
  onClearAndRemoveServiceLine,
  onCellChange,
  onCellFocus,
  onCellBlur,
  onFocusDay,
  isFullyLockedInPeriod,
  onToggleLock,
}: TimesheetDesktopGridProps) {
  const { t } = useTranslation(["timesheet"]);

  // Month view crams up to 31 day columns into the same viewport Week view only needs
  // 7 for, so it sizes its columns differently: the table is `table-fixed`, the first
  // and Total columns have set widths and the day columns (no width of their own) split
  // what is left equally, so a wider window gives wider days instead of empty space.
  // A table-wide `min-width` (first + Total + 36px per day) stops them shrinking below
  // a readable cell, and overflow-x-auto below takes over from there, the sticky first
  // and last columns staying in view. Around the table the page spends 90px (56 nav
  // rail, 32 padding, 2 border), so with the 36px floor a full month fits from a
  // 1446px window up, which is why the first column is 176px (--grid-first) below a
  // 1600px window and 208px from there: at 1600px it still leaves each day about 40px.
  // Names that no longer fit are truncated with the full text on hover (`title`); the
  // fixed layout is also what makes `truncate` work, as the cell takes the column's
  // width instead of growing to the longest text (356px on Reporting once).
  // Week view keeps its original automatic layout and widths: it already fits.
  const isMonth = periodType === "month";
  const dayColWidth = isMonth ? undefined : "min-w-16";
  const firstColWidth = isMonth ? "w-[var(--grid-first)]" : "w-60 min-w-60 max-w-60";
  const lastColWidth = isMonth ? "w-16" : "min-w-20";
  // A day cell is a td around a number input, and its paddings and the input's 2px of
  // (transparent) border are spent from the column's width: 18px of it at the old
  // p-1/p-1, which at 36px would leave "12.5" (27px of text) 18px. Month keeps 2px of td
  // padding per side and none on the input, leaving 30px; vertical padding is unchanged
  // so the rows keep their height.
  const dayHeadPadding = isMonth ? "px-1 py-2" : "p-2";
  const dayCellPadding = isMonth ? "px-0.5 py-1" : "p-1";
  const dayInputPadding = isMonth ? "px-0 py-1" : "p-1";
  const dayTotalPadding = isMonth ? "px-0.5 py-2" : "p-2";

  return (
    <div className="hidden flex-col gap-4 p-4 md:flex">
      <div
        className={cn(
          "overflow-x-auto rounded-md border",
          isMonth && "[--grid-first:11rem] min-[1600px]:[--grid-first:13rem]",
        )}
      >
        <table
          className={cn("w-full border-collapse text-sm", isMonth && "table-fixed")}
          style={
            isMonth
              ? { minWidth: `calc(var(--grid-first) + 4rem + ${days.length} * 2.25rem)` }
              : undefined
          }
        >
          <thead>
            <tr>
              <th
                className={cn(
                  "sticky left-0 top-0 z-30 border-b border-r bg-background p-2 text-left",
                  firstColWidth,
                )}
              >
                {t("Timesheet")}
              </th>
              {days.map((day) => {
                const dayKey = toDayKey(day);
                return (
                  <th
                    key={dayKey}
                    className={cn(
                      "sticky top-0 z-20 border-b text-center font-medium",
                      dayHeadPadding,
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
              <tr key={`${line.user_id}__${line.service_line_id}`}>
                <td
                  className={cn(
                    "sticky left-0 z-10 border-b border-r border-l-4 bg-background p-2",
                    firstColWidth,
                    serviceLineBorderColor(index),
                  )}
                >
                  <div className="flex items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium" title={line.project_name}>
                        {line.project_name}
                      </p>
                      <p
                        className="truncate text-xs text-muted-foreground"
                        title={line.service_line_name ?? t("(unnamed service line)")}
                      >
                        {line.service_line_name ?? t("(unnamed service line)")}
                      </p>
                      {/* Reporting only: a row here can belong to any consultant,
                          not just one implicit owner, so the label needs a third
                          line to disambiguate. */}
                      {line.consultant_name && (
                        <p
                          className="truncate text-xs text-muted-foreground"
                          title={line.consultant_name}
                        >
                          {line.consultant_name}
                        </p>
                      )}
                    </div>
                    {isFullyLockedInPeriod && onToggleLock && (
                      <LockServiceLineControl
                        isFullyLocked={isFullyLockedInPeriod(line.user_id, line.service_line_id)}
                        onToggle={() => onToggleLock(line.user_id, line.service_line_id)}
                      />
                    )}
                    {hasEntriesInPeriod &&
                      hasLockedEntriesInPeriod &&
                      onRemoveServiceLine &&
                      onClearAndRemoveServiceLine && (
                        <RemoveServiceLineControl
                          hasEntries={hasEntriesInPeriod(line.user_id, line.service_line_id)}
                          hasLockedEntries={hasLockedEntriesInPeriod(
                            line.user_id,
                            line.service_line_id,
                          )}
                          isUnassigned={isUnassignedInPeriod(line.user_id, line.service_line_id)}
                          periodLabel={periodLabel}
                          onRemove={() => onRemoveServiceLine(line.user_id, line.service_line_id)}
                          onConfirmedClear={() =>
                            onClearAndRemoveServiceLine(line.user_id, line.service_line_id)
                          }
                        />
                      )}
                  </div>
                </td>
                {days.map((day) => {
                  const dayKey = toDayKey(day);
                  const key = cellKey(line.user_id, line.service_line_id, dayKey);
                  const cell = entries[key];
                  const locked = cell?.is_locked ?? false;
                  const unassigned =
                    !locked && isUnassignedInPeriod(line.user_id, line.service_line_id);
                  const weekend = isWeekend(day);
                  // Resolved to a single class, not left as several `cn()` entries that
                  // could combine: `cn()`/`tailwind-merge` treats same-property
                  // background-color utilities as conflicting and silently drops all but
                  // the last one, so e.g. `isWeekend && "bg-muted/40"` plus
                  // `locked && "bg-slate-200"` on the same weekend+locked cell would only
                  // ever render the slate, losing the weekend shading entirely. Each branch
                  // here already bakes the weekend variant in, so there's nothing left to
                  // merge/collide. Locked still wins over unassigned if both apply.
                  const backgroundClass = locked
                    ? lockedCellClass(weekend)
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
                      className={cn("border-b text-center", dayCellPadding, backgroundClass)}
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
                            ? (unassignedTooltip?.(line.user_id, line.service_line_id) ??
                              t(
                                "This consultant is no longer assigned to this service line: read-only.",
                              ))
                            : undefined
                        }
                        value={cell?.hours ?? ""}
                        onChange={(e) =>
                          onCellChange(line.user_id, line.service_line_id, dayKey, e.target.value)
                        }
                        onBlur={(e) =>
                          onCellBlur(
                            line.user_id,
                            line.service_line_id,
                            dayKey,
                            e.currentTarget.validity.badInput,
                          )
                        }
                        onFocus={() => {
                          onCellFocus(line.user_id, line.service_line_id, dayKey);
                          onFocusDay(dayKey);
                        }}
                        aria-label={t("Hours")}
                        className={cn(
                          "w-full rounded border border-transparent bg-transparent text-center text-sm outline-none transition-colors",
                          dayInputPadding,
                          // At-rest + hover affordance for editable cells only (see
                          // conversation before this change): reuses this project's
                          // own tokens: bg-muted is already used for weekend shading
                          // in this same grid, hover:bg-secondary/50 is the exact
                          // convention TableRow (ui/table.tsx) already uses elsewhere.
                          // `enabled:` scopes both so a locked cell stays visually
                          // flat, distinguishing editable from locked at a glance.
                          "enabled:bg-muted/20 enabled:hover:bg-secondary/50",
                          // `!` (important) here isn't decorative: without it, focus
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
                  {formatHours(serviceLineTotal(line.user_id, line.service_line_id)) || "0"}h
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
                      "text-center font-medium",
                      dayTotalPadding,
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

      {onAddServiceLine && (
        <>
          {shouldShowAddLineHint(serviceLines.length, addOptions?.length) && (
            <p className="text-sm text-muted-foreground">
              {t(
                "No service lines added yet. Use “Add service line” below to start logging time.",
              )}
            </p>
          )}
          <AddServiceLineSelect options={addOptions ?? []} onAdd={onAddServiceLine} />
        </>
      )}
    </div>
  );
}
