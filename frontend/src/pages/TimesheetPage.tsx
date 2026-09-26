import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { listEligibleServiceLines, listTimeEntries } from "@/api/timeEntries";
import { TimesheetDesktopGrid } from "@/components/timesheet/TimesheetDesktopGrid";
import { TimesheetHeader } from "@/components/timesheet/TimesheetHeader";
import { TimesheetMobileView } from "@/components/timesheet/TimesheetMobileView";
import { useAuth } from "@/hooks/useAuth";
import { useTimesheetGrid } from "@/hooks/useTimesheetGrid";
import {
  defaultPeriodDate,
  defaultPeriodType,
  formatMonthLabel,
  getIsoWeekNumber,
  getPeriodDays,
  parseDayKey,
  shiftPeriod,
  startOfMonth,
  startOfWeekMonday,
  toDayKey,
} from "@/lib/timesheetDates";
import { sumHours } from "@/lib/timesheetHours";
import type { EligibleServiceLine, PeriodType, TimeEntry } from "@/types/timesheet";

export function TimesheetPage() {
  const { t } = useTranslation(["timesheet"]);
  const { user } = useAuth();

  // Week on mobile, Month on desktop/tablet: a one-time default computed at
  // mount from the same `md:` breakpoint the views themselves switch on, not a
  // live-synced setting.
  const [periodType, setPeriodType] = useState<PeriodType>(defaultPeriodType);
  const [periodDate, setPeriodDate] = useState<Date>(defaultPeriodDate);
  const [selectedKey, setSelectedKey] = useState<string>(() => toDayKey(defaultPeriodDate()));

  const [initialEntries, setInitialEntries] = useState<TimeEntry[]>([]);
  const [eligibleLines, setEligibleLines] = useState<EligibleServiceLine[]>([]);
  const [monthToDateTotal, setMonthToDateTotal] = useState(0);

  const days = useMemo(() => getPeriodDays(periodType, periodDate), [periodType, periodDate]);

  useEffect(() => {
    listEligibleServiceLines()
      .then((res) => setEligibleLines(res.items))
      .catch((err: unknown) => {
        toast.error(
          err instanceof ApiError ? err.message : t("Failed to load service lines."),
        );
      });
  }, [t]);

  useEffect(() => {
    const start = toDayKey(days[0]);
    const end = toDayKey(days[days.length - 1]);
    listTimeEntries(start, end)
      .then((res) => setInitialEntries(res.items))
      .catch((err: unknown) => {
        toast.error(err instanceof ApiError ? err.message : t("Failed to load time entries."));
      });
    // `days` is derived from periodType/periodDate every render, but its identity
    // changes each time too: depend on the primitives that actually drive it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodType, periodDate, t]);

  useEffect(() => {
    const selectedDate = parseDayKey(selectedKey);
    const start = toDayKey(startOfMonth(selectedDate));
    listTimeEntries(start, selectedKey)
      .then((res) => setMonthToDateTotal(sumHours(res.items.map((i) => i.hours))))
      .catch(() => {
        // Non-critical summary figure: a failed fetch just leaves the last known total.
      });
  }, [selectedKey]);

  const {
    entries,
    serviceLines,
    addOptions,
    hasEntriesInPeriod,
    hasLockedEntriesInPeriod,
    isUnassignedInPeriod,
    dayTotal,
    serviceLineTotal,
    periodTotal,
    handleAddServiceLine,
    handleRemoveServiceLine,
    handleClearAndRemoveServiceLine,
    handleCellChange,
    handleCellFocus,
    handleCellBlur,
  } = useTimesheetGrid({ days, initialEntries, eligibleLines, rowOwnerId: user?.id ?? "" });

  // Same label TimesheetHeader itself shows (e.g. "August 2026" / "Week 34"): used
  // by the "Removing a service line" confirmation dialog to name exactly the range
  // about to be cleared.
  const periodLabel =
    periodType === "month"
      ? formatMonthLabel(periodDate)
      : t("Week {{number}}", { number: getIsoWeekNumber(periodDate) });

  function handlePeriodTypeChange(next: PeriodType) {
    const anchor = parseDayKey(selectedKey);
    const nextPeriodDate = next === "week" ? startOfWeekMonday(anchor) : startOfMonth(anchor);
    setPeriodType(next);
    setPeriodDate(nextPeriodDate);
    setSelectedKey(toDayKey(nextPeriodDate));
  }

  function handleNavigate(direction: 1 | -1) {
    const nextPeriodDate = shiftPeriod(periodType, periodDate, direction);
    setPeriodDate(nextPeriodDate);
    const nextDays = getPeriodDays(periodType, nextPeriodDate);
    const boundary = direction === 1 ? nextDays[0] : nextDays[nextDays.length - 1];
    setSelectedKey(toDayKey(boundary));
  }

  return (
    <div className="flex flex-col">
      <TimesheetHeader
        periodType={periodType}
        periodDate={periodDate}
        periodTotal={periodTotal}
        onPeriodTypeChange={handlePeriodTypeChange}
        onNavigate={handleNavigate}
      />

      <TimesheetMobileView
        days={days}
        selectedKey={selectedKey}
        onSelectDay={setSelectedKey}
        serviceLines={serviceLines}
        entries={entries}
        dayTotal={dayTotal}
        monthToDateTotal={monthToDateTotal}
        periodLabel={periodLabel}
        addOptions={addOptions}
        onAddServiceLine={handleAddServiceLine}
        hasEntriesInPeriod={hasEntriesInPeriod}
        hasLockedEntriesInPeriod={hasLockedEntriesInPeriod}
        isUnassignedInPeriod={isUnassignedInPeriod}
        onRemoveServiceLine={handleRemoveServiceLine}
        onClearAndRemoveServiceLine={handleClearAndRemoveServiceLine}
        onCellChange={handleCellChange}
        onCellFocus={handleCellFocus}
        onCellBlur={handleCellBlur}
      />

      <TimesheetDesktopGrid
        periodType={periodType}
        days={days}
        serviceLines={serviceLines}
        entries={entries}
        dayTotal={dayTotal}
        serviceLineTotal={serviceLineTotal}
        periodTotal={periodTotal}
        periodLabel={periodLabel}
        addOptions={addOptions}
        onAddServiceLine={handleAddServiceLine}
        hasEntriesInPeriod={hasEntriesInPeriod}
        hasLockedEntriesInPeriod={hasLockedEntriesInPeriod}
        isUnassignedInPeriod={isUnassignedInPeriod}
        onRemoveServiceLine={handleRemoveServiceLine}
        onClearAndRemoveServiceLine={handleClearAndRemoveServiceLine}
        onCellChange={handleCellChange}
        onCellFocus={handleCellFocus}
        onCellBlur={handleCellBlur}
        onFocusDay={setSelectedKey}
      />
    </div>
  );
}
