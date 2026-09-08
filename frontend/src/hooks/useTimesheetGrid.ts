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

// Per-item error codes the bulk PUT /time-entries can report — see TimeEntryUpsertResult.
function errorMessage(error: TimeEntryUpsertResult["error"], t: (key: string) => string): string {
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
  // Unfiltered — see ManagedConsultantOut on the backend and EligibleServiceLine
  // on My Timesheet's own fetch. Used both for the Add-dropdown and for the
  // "still currently assigned" per-row check (isUnassignedInPeriod below).
  eligibleLines: EligibleServiceLine[];
  // undefined = the caller's own entries (My Timesheet). Set to a consultant's id
  // on the Validation screen, so cell edits are sent as a project_manager
  // override instead.
  ownerUserId?: string;
}

// Shared state/logic behind both My Timesheet and each consultant block on the
// Validation screen (one shared mechanism, not two) — entries, the per-period
// "added service lines" set, the visible service-line list, and every
// cell/add/remove handler. The two screens differ only in what they pass in
// (initialEntries/eligibleLines/ownerUserId) and which extra chrome (lock
// control, consultant header) they render around this.
export function useTimesheetGrid({ days, initialEntries, eligibleLines, ownerUserId }: UseTimesheetGridOptions) {
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
    setAddedServiceLines([]);
  }, [initialEntries]);

  // Checks live `entries` state directly — kept correctly in sync on every
  // mutation (blur-save, blur-delete, and the clear-on-remove bulk call alike) —
  // rather than `historicalServiceLines`, which is only a snapshot from the last
  // load and goes stale the moment a line's entries change locally without a
  // fresh fetch.
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

  // Every day in the period is locked for this line — the icon/action semantics
  // this drives (Lock shown unless *every* day is locked) live in
  // LockServiceLineControl; this is just the underlying fact.
  const isFullyLockedInPeriod = useCallback(
    (serviceLineId: string) =>
      days.every((day) => entries[cellKey(serviceLineId, toDayKey(day))]?.is_locked === true),
    [days, entries],
  );

  // The entry's owner is no longer currently assigned to this service line —
  // read-only regardless of `is_locked`, on both My Timesheet (viewing one's own
  // historical data) and Validation (a consultant's since-unassigned line) alike.
  const isUnassignedInPeriod = useCallback(
    (serviceLineId: string) =>
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
      (line) => addedIds.has(line.service_line_id) || hasEntriesInPeriod(line.service_line_id),
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

  function handleAddServiceLine(serviceLineId: string) {
    const line = eligibleLines.find((option) => option.service_line_id === serviceLineId);
    if (!line) return;
    setAddedServiceLines((prev) =>
      prev.some((l) => l.service_line_id === serviceLineId) ? prev : [...prev, line],
    );
  }

  // No-data branch — a line can only be visible with nothing logged this period
  // because it's in this period's `addedServiceLines`, so removing it here is
  // just undoing that add. No separate "removed" state to track.
  function handleRemoveServiceLine(serviceLineId: string) {
    setAddedServiceLines((prev) => prev.filter((l) => l.service_line_id !== serviceLineId));
  }

  // Confirmed-destructive branch — this is only ever invoked once
  // RemoveServiceLineControl has already confirmed via its dialog, for a line
  // with logged, unlocked time this period. Clears every day in the current
  // period that has an entry for this line, in one bulk call — never one request
  // per day.
  async function handleClearAndRemoveServiceLine(serviceLineId: string) {
    const targetDayKeys = days
      .map((day) => toDayKey(day))
      .filter((dayKey) => entries[cellKey(serviceLineId, dayKey)] !== undefined);

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
          ...(ownerUserId ? { user_id: ownerUserId } : {}),
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

      // Fully cleared — also drop it from this period's "added" set in case it
      // happened to be there too (added this period, then given data, then
      // removed); harmless no-op filter if it wasn't.
      setAddedServiceLines((prev) => prev.filter((l) => l.service_line_id !== serviceLineId));
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
      // never a bare object.
      const [result] = await upsertTimeEntries([
        {
          service_line_id: serviceLineId,
          date: dayKey,
          hours: corrected,
          ...(ownerUserId ? { user_id: ownerUserId } : {}),
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

  // Merges a PUT /time-entries/lock response (the whole period's rows for one
  // service line) into local state. Locking can materialize new gap-day rows and
  // unlocking can delete gap-day rows entirely, so this both upserts and deletes
  // rather than only patching `is_locked` in place.
  function applyLockResult(serviceLineId: string, updated: TimeEntry[], wasLockAction: boolean) {
    setEntries((prev) => {
      const next = { ...prev };
      const updatedByDate = new Map(updated.map((entry) => [entry.date, entry]));
      for (const day of days) {
        const dayKey = toDayKey(day);
        const key = cellKey(serviceLineId, dayKey);
        const entry = updatedByDate.get(dayKey);
        if (entry) {
          next[key] = { hours: formatHours(Number(entry.hours)), is_locked: entry.is_locked };
        } else if (!wasLockAction) {
          // Unlock deleted this gap-day row (it had no real hours) — see
          // set_service_line_lock's unlock branch on the backend.
          delete next[key];
        }
      }
      return next;
    });
  }

  return {
    entries,
    serviceLines,
    addOptions,
    hasEntriesInPeriod,
    hasLockedEntriesInPeriod,
    isFullyLockedInPeriod,
    isUnassignedInPeriod,
    dayTotal,
    serviceLineTotal,
    periodTotal,
    handleAddServiceLine,
    handleRemoveServiceLine,
    handleClearAndRemoveServiceLine,
    handleCellChange,
    handleCellBlur,
    applyLockResult,
  };
}
