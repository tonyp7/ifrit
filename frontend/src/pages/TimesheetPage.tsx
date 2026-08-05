import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { listEligibleServiceLines, listTimeEntries, upsertTimeEntry } from "@/api/timeEntries";
import { TimesheetDesktopGrid } from "@/components/timesheet/TimesheetDesktopGrid";
import { TimesheetHeader } from "@/components/timesheet/TimesheetHeader";
import { TimesheetMobileView } from "@/components/timesheet/TimesheetMobileView";
import {
  getPeriodDays,
  parseDayKey,
  shiftPeriod,
  startOfMonth,
  startOfWeekMonday,
  toDayKey,
} from "@/lib/timesheetDates";
import { cellKey, formatHours, normalizeHours, sumHours } from "@/lib/timesheetHours";
import type {
  EligibleServiceLine,
  EntryCell,
  PeriodType,
  ServiceLineRow,
} from "@/types/timesheet";

export function TimesheetPage() {
  const { t } = useTranslation(["timesheet"]);

  const [periodType, setPeriodType] = useState<PeriodType>("week");
  const [periodDate, setPeriodDate] = useState<Date>(() => startOfWeekMonday(new Date()));
  const [selectedKey, setSelectedKey] = useState<string>(() =>
    toDayKey(startOfWeekMonday(new Date())),
  );

  const [entries, setEntries] = useState<Record<string, EntryCell>>({});
  const [historicalServiceLines, setHistoricalServiceLines] = useState<ServiceLineRow[]>(
    [],
  );
  const [addedServiceLines, setAddedServiceLines] = useState<ServiceLineRow[]>([]);
  const [removedServiceLineIds, setRemovedServiceLineIds] = useState<Set<string>>(
    new Set(),
  );
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
        toast.error(
          err instanceof ApiError ? err.message : t("Failed to load time entries."),
        );
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
    return merged.filter((line) => !removedServiceLineIds.has(line.service_line_id));
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

    try {
      const result = await upsertTimeEntry({
        service_line_id: serviceLineId,
        date: dayKey,
        hours: corrected,
      });
      setEntries((prev) => {
        const next = { ...prev };
        if (result) {
          next[key] = { hours: formatHours(Number(result.hours)), is_locked: result.is_locked };
        } else {
          delete next[key];
        }
        return next;
      });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : t("Failed to save time entry."),
      );
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
        addOptions={addOptions}
        onAddServiceLine={handleAddServiceLine}
        onRemoveServiceLine={handleRemoveServiceLine}
        onCellChange={handleCellChange}
        onCellBlur={handleCellBlur}
      />

      <TimesheetDesktopGrid
        days={days}
        serviceLines={serviceLines}
        entries={entries}
        dayTotal={dayTotal}
        serviceLineTotal={serviceLineTotal}
        periodTotal={periodTotal}
        addOptions={addOptions}
        onAddServiceLine={handleAddServiceLine}
        onRemoveServiceLine={handleRemoveServiceLine}
        onCellChange={handleCellChange}
        onCellBlur={handleCellBlur}
      />
    </div>
  );
}
