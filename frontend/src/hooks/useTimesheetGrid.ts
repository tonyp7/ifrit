import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { upsertTimeEntries } from "@/api/timeEntries";
import { toDayKey } from "@/lib/timesheetDates";
import { cellKey, formatHours, normalizeHours, sumHours } from "@/lib/timesheetHours";
import { sortServiceLines } from "@/lib/timesheetServiceLines";
import type {
  EligibleServiceLine,
  EntryCell,
  ServiceLineRow,
  TimeEntry,
  TimeEntryUpsertResult,
} from "@/types/timesheet";

// Per-item error codes the bulk PUT /time-entries can report — see
// TimeEntryUpsertResult. Exported for useReportGrid, which hits the exact same
// error codes on its own per-row cell edits.
export function errorMessage(
  error: TimeEntryUpsertResult["error"],
  t: (key: string) => string,
): string {
  if (error === "locked") return t("This entry has been locked and can't be changed.");
  if (error === "not_eligible") return t("You're not assigned to this service line.");
  if (error === "not_authorized") return t("You're not authorized to edit this entry.");
  return t("Failed to save time entry.");
}

export interface UseTimesheetGridOptions {
  days: Date[];
  // Raw entries for exactly this owner over some window covering `days` — a new
  // array reference re-seeds all local state below (see the effect below), so
  // callers should only produce a new one when they actually want a reset (a
  // period change, or an initial/refetched load) — never on every render.
  initialEntries: TimeEntry[];
  // Unfiltered — see EligibleServiceLine, My Timesheet's own fetch. Used both for the
  // Add-dropdown and for the
  // "still currently assigned" per-row check (isUnassignedInPeriod below).
  eligibleLines: EligibleServiceLine[];
  // The caller's own id — used to key local `entries` state (see cellKey) and stamped
  // onto every ServiceLineRow this hook builds.
  rowOwnerId: string;
}

// Shared state/logic behind My Timesheet — entries, the per-period "added service
// lines" set, the visible service-line list, and every cell/add/remove handler.
export function useTimesheetGrid({
  days,
  initialEntries,
  eligibleLines,
  rowOwnerId,
}: UseTimesheetGridOptions) {
  const { t } = useTranslation(["timesheet"]);

  const [entries, setEntries] = useState<Record<string, EntryCell>>({});
  const [historicalServiceLines, setHistoricalServiceLines] = useState<ServiceLineRow[]>([]);
  // Lines added via "Add service line" while *this* period is the one being
  // viewed — deliberately reset whenever `initialEntries` is re-seeded (a period
  // change), not session-wide.
  const [addedServiceLines, setAddedServiceLines] = useState<ServiceLineRow[]>([]);

  useEffect(() => {
    const nextEntries: Record<string, EntryCell> = {};
    const seen = new Set<string>();
    const historical: ServiceLineRow[] = [];
    for (const item of initialEntries) {
      nextEntries[cellKey(rowOwnerId, item.service_line_id, item.date)] = {
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
          user_id: rowOwnerId,
        });
      }
    }
    setEntries(nextEntries);
    setHistoricalServiceLines(historical);
    setAddedServiceLines([]);
  }, [initialEntries, rowOwnerId]);

  // Checks live `entries` state directly — kept correctly in sync on every
  // mutation (blur-save, blur-delete, and the clear-on-remove bulk call alike) —
  // rather than `historicalServiceLines`, which is only a snapshot from the last
  // load and goes stale the moment a line's entries change locally without a
  // fresh fetch.
  // Every callback below that identifies "which row" takes a leading `userId`
  // param, purely so its signature matches useReportGrid's — both get passed into
  // the exact same TimesheetDesktopGrid/TimesheetMobileView props. This hook is
  // still one-owner-per-instance (My Timesheet), so the passed userId
  // always equals `rowOwnerId` here; it's accepted and ignored rather than
  // threaded through, since this hook already has its own closed-over id.
  const hasEntriesInPeriod = useCallback(
    (_userId: string, serviceLineId: string) =>
      days.some((day) => entries[cellKey(rowOwnerId, serviceLineId, toDayKey(day))] !== undefined),
    [days, entries, rowOwnerId],
  );

  const hasLockedEntriesInPeriod = useCallback(
    (_userId: string, serviceLineId: string) =>
      days.some(
        (day) => entries[cellKey(rowOwnerId, serviceLineId, toDayKey(day))]?.is_locked === true,
      ),
    [days, entries, rowOwnerId],
  );

  // The entry's owner is no longer currently assigned to this service line —
  // read-only regardless of `is_locked` (viewing one's own historical data on a
  // since-unassigned line).
  const isUnassignedInPeriod = useCallback(
    (_userId: string, serviceLineId: string) =>
      !eligibleLines.some((line) => line.service_line_id === serviceLineId),
    [eligibleLines],
  );

  const serviceLines = useMemo(() => {
    const merged: ServiceLineRow[] = [...addedServiceLines];
    const addedIds = new Set(addedServiceLines.map((l) => l.service_line_id));
    for (const line of historicalServiceLines) {
      if (!addedIds.has(line.service_line_id)) merged.push(line);
    }
    // A line shows if it's this period's "added" set (addedIds — unconditional,
    // that's the whole point of adding it) or has any entry this period
    // (hasEntriesInPeriod, checked against live `entries` rather than
    // historicalServiceLines directly — see its own comment above). No separate
    // suppression/removed state needed.
    const visible = merged.filter(
      (line) =>
        addedIds.has(line.service_line_id) ||
        hasEntriesInPeriod(line.user_id, line.service_line_id),
    );
    // Ascending by project name, then service line name — a stable order
    // independent of add/discovery order or which period's date window was last
    // fetched.
    return sortServiceLines(visible);
  }, [addedServiceLines, historicalServiceLines, hasEntriesInPeriod]);

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
        serviceLines.map(
          (line) => entries[cellKey(rowOwnerId, line.service_line_id, dayKey)]?.hours,
        ),
      ),
    [serviceLines, entries, rowOwnerId],
  );

  const serviceLineTotal = useCallback(
    (_userId: string, serviceLineId: string) =>
      sumHours(
        days.map((day) => entries[cellKey(rowOwnerId, serviceLineId, toDayKey(day))]?.hours),
      ),
    [days, entries, rowOwnerId],
  );

  const periodTotal = useMemo(
    () =>
      serviceLines.reduce(
        (sum, line) => sum + serviceLineTotal(line.user_id, line.service_line_id),
        0,
      ),
    [serviceLines, serviceLineTotal],
  );

  function handleAddServiceLine(serviceLineId: string) {
    const line = eligibleLines.find((option) => option.service_line_id === serviceLineId);
    if (!line) return;
    setAddedServiceLines((prev) =>
      prev.some((l) => l.service_line_id === serviceLineId)
        ? prev
        : [...prev, { ...line, user_id: rowOwnerId }],
    );
  }

  // No-data branch — a line can only be visible with nothing logged this period
  // because it's in this period's `addedServiceLines`, so removing it here is
  // just undoing that add. No separate "removed" state to track.
  function handleRemoveServiceLine(_userId: string, serviceLineId: string) {
    setAddedServiceLines((prev) => prev.filter((l) => l.service_line_id !== serviceLineId));
  }

  // Confirmed-destructive branch — this is only ever invoked once
  // RemoveServiceLineControl has already confirmed via its dialog, for a line
  // with logged, unlocked time this period. Clears every day in the current
  // period that has an entry for this line, in one bulk call — never one request
  // per day.
  async function handleClearAndRemoveServiceLine(_userId: string, serviceLineId: string) {
    const targetDayKeys = days
      .map((day) => toDayKey(day))
      .filter((dayKey) => entries[cellKey(rowOwnerId, serviceLineId, dayKey)] !== undefined);

    if (targetDayKeys.length === 0) {
      // Nothing to clear — shouldn't normally happen (the confirm dialog only opens
      // when hasEntriesInPeriod is true), but stay safe rather than no-op silently.
      setAddedServiceLines((prev) => prev.filter((l) => l.service_line_id !== serviceLineId));
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
          const key = cellKey(rowOwnerId, serviceLineId, result.date);
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

      // Fully cleared — also drop it from this period's "added" set in case it
      // happened to be there too (added this period, then given data, then
      // removed); harmless no-op filter if it wasn't.
      setAddedServiceLines((prev) => prev.filter((l) => l.service_line_id !== serviceLineId));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to remove service line."));
    }
  }

  function handleCellChange(
    _userId: string,
    serviceLineId: string,
    dayKey: string,
    value: string,
  ) {
    const key = cellKey(rowOwnerId, serviceLineId, dayKey);
    setEntries((prev) => ({
      ...prev,
      [key]: { hours: value, is_locked: prev[key]?.is_locked ?? false },
    }));
  }

  async function handleCellBlur(_userId: string, serviceLineId: string, dayKey: string) {
    const key = cellKey(rowOwnerId, serviceLineId, dayKey);
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
      // never a bare object.
      const [result] = await upsertTimeEntries([
        {
          service_line_id: serviceLineId,
          date: dayKey,
          hours: corrected,
        },
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

  return {
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
    handleCellBlur,
  };
}
