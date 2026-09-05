import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { listEligibleServiceLines, listTimeEntries, upsertTimeEntries } from "@/api/timeEntries";
import { TimesheetDesktopGrid } from "@/components/timesheet/TimesheetDesktopGrid";
import { TimesheetHeader } from "@/components/timesheet/TimesheetHeader";
import { TimesheetMobileView } from "@/components/timesheet/TimesheetMobileView";
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
import { cellKey, formatHours, normalizeHours, sumHours } from "@/lib/timesheetHours";
import { sortServiceLines } from "@/lib/timesheetServiceLines";
import type {
  EligibleServiceLine,
  EntryCell,
  PeriodType,
  ServiceLineRow,
  TimeEntryUpsertResult,
} from "@/types/timesheet";

// Per-item error codes the bulk PUT /time-entries can report — see
// docs/requirements/timesheet.md's "API contract" and TimeEntryUpsertResult.
function errorMessage(error: TimeEntryUpsertResult["error"], t: (key: string) => string): string {
  if (error === "locked") return t("This entry has been locked and can't be changed.");
  if (error === "not_eligible") return t("You're not assigned to this service line.");
  return t("Failed to save time entry.");
}

export function TimesheetPage() {
  const { t } = useTranslation(["timesheet"]);

  // Week on mobile, Month on desktop/tablet — a one-time default computed at
  // mount from the same `md:` breakpoint the views themselves switch on, not a
  // live-synced setting (see docs/requirements/timesheet.md#my-timesheet-clocking).
  const [periodType, setPeriodType] = useState<PeriodType>(defaultPeriodType);
  const [periodDate, setPeriodDate] = useState<Date>(defaultPeriodDate);
  const [selectedKey, setSelectedKey] = useState<string>(() => toDayKey(defaultPeriodDate()));

  const [entries, setEntries] = useState<Record<string, EntryCell>>({});
  const [historicalServiceLines, setHistoricalServiceLines] = useState<ServiceLineRow[]>([]);
  const [addedServiceLines, setAddedServiceLines] = useState<ServiceLineRow[]>([]);
  const [removedServiceLineIds, setRemovedServiceLineIds] = useState<Set<string>>(new Set());
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
      .then((res) => {
        const nextEntries: Record<string, EntryCell> = {};
        const seen = new Set<string>();
        const historical: ServiceLineRow[] = [];
        for (const item of res.items) {
          nextEntries[cellKey(item.service_line_id, item.date)] = {
            hours: formatHours(Number(item.hours)),
            is_locked: item.is_locked,
          };
          if (!seen.has(item.service_line_id)) {
            seen.add(item.service_line_id);
            historical.push({
              service_line_id: item.service_line_id,
              service_line_name: item.service_line_name,
              project_id: item.project_id,
              project_name: item.project_name,
            });
          }
        }
        setEntries(nextEntries);
        setHistoricalServiceLines(historical);
      })
      .catch((err: unknown) => {
        toast.error(err instanceof ApiError ? err.message : t("Failed to load time entries."));
      });
    // `days` is derived from periodType/periodDate every render, but its identity
    // changes each time too — depend on the primitives that actually drive it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodType, periodDate, t]);

  useEffect(() => {
    const selectedDate = parseDayKey(selectedKey);
    const start = toDayKey(startOfMonth(selectedDate));
    listTimeEntries(start, selectedKey)
      .then((res) => setMonthToDateTotal(sumHours(res.items.map((i) => i.hours))))
      .catch(() => {
        // Non-critical summary figure — a failed fetch just leaves the last known total.
      });
  }, [selectedKey]);

  const serviceLines = useMemo(() => {
    const merged: ServiceLineRow[] = [...addedServiceLines];
    const addedIds = new Set(addedServiceLines.map((l) => l.service_line_id));
    for (const line of historicalServiceLines) {
      if (!addedIds.has(line.service_line_id)) merged.push(line);
    }
    // `historicalServiceLines` already only contains lines with a real time_entries
    // row for *this* period's date range (see the listTimeEntries effect above) —
    // so a line in it can never be hidden by the removed-set, even if it was
    // removed earlier in the session for a different period. The app must never
    // hide a service line that has entries for the period being viewed (see
    // docs/requirements/timesheet.md#state) — this is re-evaluated on every period
    // change, not a one-time decision, since historicalServiceLines is refetched
    // per period too.
    const historicalIds = new Set(historicalServiceLines.map((l) => l.service_line_id));
    const visible = merged.filter(
      (line) =>
        historicalIds.has(line.service_line_id) ||
        !removedServiceLineIds.has(line.service_line_id),
    );
    // Ascending by project name, then service line name — a stable order
    // independent of add/discovery order or which period's date window was
    // last fetched (see docs/requirements/timesheet.md#state).
    return sortServiceLines(visible);
  }, [addedServiceLines, historicalServiceLines, removedServiceLineIds]);

  const addOptions = useMemo(
    () =>
      eligibleLines.filter(
        (option) => !serviceLines.some((l) => l.service_line_id === option.service_line_id),
      ),
    [eligibleLines, serviceLines],
  );

  const dayTotal = useCallback(
    (dayKey: string) =>
      sumHours(
        serviceLines.map((line) => entries[cellKey(line.service_line_id, dayKey)]?.hours),
      ),
    [serviceLines, entries],
  );

  const serviceLineTotal = useCallback(
    (serviceLineId: string) =>
      sumHours(days.map((day) => entries[cellKey(serviceLineId, toDayKey(day))]?.hours)),
    [days, entries],
  );

  const periodTotal = useMemo(
    () => serviceLines.reduce((sum, line) => sum + serviceLineTotal(line.service_line_id), 0),
    [serviceLines, serviceLineTotal],
  );

  // Same label TimesheetHeader itself shows (e.g. "August 2026" / "Week 34") — used
  // by the "Removing a service line" confirmation dialog to name exactly the range
  // about to be cleared (see docs/requirements/timesheet.md#interactions--input-rules).
  const periodLabel =
    periodType === "month"
      ? formatMonthLabel(periodDate)
      : t("Week {{number}}", { number: getIsoWeekNumber(periodDate) });

  const hasEntriesInPeriod = useCallback(
    (serviceLineId: string) =>
      days.some((day) => entries[cellKey(serviceLineId, toDayKey(day))] !== undefined),
    [days, entries],
  );

  const hasLockedEntriesInPeriod = useCallback(
    (serviceLineId: string) =>
      days.some((day) => entries[cellKey(serviceLineId, toDayKey(day))]?.is_locked === true),
    [days, entries],
  );

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

  function handleAddServiceLine(serviceLineId: string) {
    const line = eligibleLines.find((option) => option.service_line_id === serviceLineId);
    if (!line) return;
    setRemovedServiceLineIds((prev) => {
      if (!prev.has(serviceLineId)) return prev;
      const next = new Set(prev);
      next.delete(serviceLineId);
      return next;
    });
    setAddedServiceLines((prev) =>
      prev.some((l) => l.service_line_id === serviceLineId) ? prev : [...prev, line],
    );
  }

  function handleRemoveServiceLine(serviceLineId: string) {
    setRemovedServiceLineIds((prev) => new Set(prev).add(serviceLineId));
  }

  // Confirmed-destructive branch (see docs/requirements/timesheet.md's "Removing a
  // service line" — this is only ever invoked once RemoveServiceLineControl has
  // already confirmed via its dialog, for a line with logged, unlocked time this
  // period). Clears every day in the current period that has an entry for this
  // line, in one bulk call — never one request per day.
  async function handleClearAndRemoveServiceLine(serviceLineId: string) {
    const targetDayKeys = days
      .map((day) => toDayKey(day))
      .filter((dayKey) => entries[cellKey(serviceLineId, dayKey)] !== undefined);

    if (targetDayKeys.length === 0) {
      // Nothing to clear — shouldn't normally happen (the confirm dialog only opens
      // when hasEntriesInPeriod is true), but stay safe rather than no-op silently.
      setRemovedServiceLineIds((prev) => new Set(prev).add(serviceLineId));
      return;
    }

    try {
      const results = await upsertTimeEntries(
        targetDayKeys.map((dayKey) => ({
          service_line_id: serviceLineId,
          date: dayKey,
          hours: "0",
        })),
      );

      setEntries((prev) => {
        const next = { ...prev };
        for (const result of results) {
          const key = cellKey(serviceLineId, result.date);
          if (result.ok) {
            delete next[key];
          } else {
            // The only rejection reason this flow can hit is "locked" (eligibility
            // is never checked for an hours=0 item — see the backend's per-item
            // logic) — most plausibly a day a project_manager locked between
            // opening the confirmation dialog and clicking Confirm. The response
            // doesn't carry a fresh `entry` for a rejected item (only `ok`/`error`),
            // so patch `is_locked` in ourselves rather than leaving this cell's
            // local state stale — otherwise RemoveServiceLineControl would keep
            // seeing this line as freely removable until a full reload.
            next[key] = { hours: next[key]?.hours ?? "", is_locked: true };
          }
        }
        return next;
      });

      const rejected = results.filter((r) => !r.ok);
      if (rejected.length > 0) {
        // The line must NOT be removed from view: it now has a locked entry this
        // period, which already makes it non-removable (RemoveServiceLineControl's
        // hasLockedEntries reflects this from the updated `entries` state above).
        toast.error(
          t(
            "Some time for this service line couldn't be cleared because it's since been locked. The service line remains visible.",
          ),
        );
        return;
      }

      setRemovedServiceLineIds((prev) => new Set(prev).add(serviceLineId));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to remove service line."));
    }
  }

  function handleCellChange(serviceLineId: string, dayKey: string, value: string) {
    const key = cellKey(serviceLineId, dayKey);
    setEntries((prev) => ({
      ...prev,
      [key]: { hours: value, is_locked: prev[key]?.is_locked ?? false },
    }));
  }

  async function handleCellBlur(serviceLineId: string, dayKey: string) {
    const key = cellKey(serviceLineId, dayKey);
    const previous = entries[key]?.hours ?? "";
    const corrected = normalizeHours(entries[key]?.hours ?? "", previous || "0");

    if (Number(corrected) === 0) {
      setEntries((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } else {
      setEntries((prev) => ({ ...prev, [key]: { hours: corrected, is_locked: false } }));
    }

    function revert() {
      setEntries((prev) => {
        const next = { ...prev };
        if (previous && Number(previous) > 0) {
          next[key] = { hours: previous, is_locked: false };
        } else {
          delete next[key];
        }
        return next;
      });
    }

    try {
      // Always an array — a single cell blur sends a one-element request/response,
      // never a bare object (see docs/requirements/timesheet.md's "API contract").
      const [result] = await upsertTimeEntries([
        { service_line_id: serviceLineId, date: dayKey, hours: corrected },
      ]);
      if (result.ok) {
        setEntries((prev) => {
          const next = { ...prev };
          if (result.entry) {
            next[key] = {
              hours: formatHours(Number(result.entry.hours)),
              is_locked: result.entry.is_locked,
            };
          } else {
            delete next[key];
          }
          return next;
        });
      } else {
        toast.error(errorMessage(result.error, t));
        revert();
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to save time entry."));
      revert();
    }
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
        onRemoveServiceLine={handleRemoveServiceLine}
        onClearAndRemoveServiceLine={handleClearAndRemoveServiceLine}
        onCellChange={handleCellChange}
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
        onRemoveServiceLine={handleRemoveServiceLine}
        onClearAndRemoveServiceLine={handleClearAndRemoveServiceLine}
        onCellChange={handleCellChange}
        onCellBlur={handleCellBlur}
        onFocusDay={setSelectedKey}
      />
    </div>
  );
}
