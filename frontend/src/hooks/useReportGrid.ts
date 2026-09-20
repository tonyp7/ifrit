import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { setServiceLineLock, upsertTimeEntries } from "@/api/timeEntries";
import { errorMessage } from "@/hooks/useTimesheetGrid";
import { toDayKey } from "@/lib/timesheetDates";
import { cellKey, formatHours, normalizeHours, sumHours } from "@/lib/timesheetHours";
import type { EntryCell, ServiceLineRow, TimesheetReportRow } from "@/types/timesheet";

export interface UseReportGridOptions {
  days: Date[];
  // Reporting's row data, one row per (consultant, service_line) pair, already
  // sorted server-side (full_name, project_name, service_line_name,
  // service_line_id). A new array reference re-seeds all local state below (see
  // the effect below), produced on every period/filter change.
  rows: TimesheetReportRow[];
}

// Reporting's counterpart to useTimesheetGrid: deliberately a separate, lighter
// hook rather than forced through that one: Reporting's row set is entirely
// filter-driven (no "Add service line"/"Remove" affordance, per its own spec), and
// a single grid instance here spans many different consultants at once, unlike
// useTimesheetGrid's one-owner-per-instance design. What IS shared: the same
// cellKey/formatHours/normalizeHours utilities, the same bulk PUT /time-entries
// and PUT /time-entries/lock endpoints, and: critically: the exact same
// TimesheetDesktopGrid/TimesheetMobileView components this hook's return value
// feeds into, via the same widened (userId, serviceLineId, ...) callback shape
// useTimesheetGrid's own handlers already use.
export function useReportGrid({ days, rows }: UseReportGridOptions) {
  const { t } = useTranslation(["timesheet"]);

  const [entries, setEntries] = useState<Record<string, EntryCell>>({});
  // Whether each (user_id, service_line_id) pair is currently assigned, per the
  // backend's narrower is_assigned rule (see TimesheetReportRowOut): what
  // isUnassignedInPeriod below reads, instead of computing eligibility
  // client-side the way useTimesheetGrid does from a fetched eligible-lines list.
  const [assignedByPair, setAssignedByPair] = useState<Record<string, boolean>>({});
  // The row's project_status, for unassignedTooltip below: already sent on
  // every row (TimesheetReportRowOut.project_status), so this needs no extra
  // fetch or backend change.
  const [projectStatusByPair, setProjectStatusByPair] = useState<Record<string, string>>({});

  const serviceLines: ServiceLineRow[] = useMemo(
    () =>
      rows.map((row) => ({
        service_line_id: row.service_line_id,
        service_line_name: row.service_line_name,
        project_id: row.project_id,
        project_name: row.project_name,
        user_id: row.user_id,
        consultant_name: row.full_name,
      })),
    [rows],
  );

  useEffect(() => {
    const nextEntries: Record<string, EntryCell> = {};
    const nextAssigned: Record<string, boolean> = {};
    const nextStatus: Record<string, string> = {};
    for (const row of rows) {
      const pairKey = `${row.user_id}__${row.service_line_id}`;
      nextAssigned[pairKey] = row.is_assigned;
      nextStatus[pairKey] = row.project_status;
      for (const item of row.entries) {
        nextEntries[cellKey(row.user_id, item.service_line_id, item.date)] = {
          hours: formatHours(Number(item.hours)),
          is_locked: item.is_locked,
        };
      }
    }
    setEntries(nextEntries);
    setAssignedByPair(nextAssigned);
    setProjectStatusByPair(nextStatus);
  }, [rows]);

  const isUnassignedInPeriod = useCallback(
    (userId: string, serviceLineId: string) =>
      assignedByPair[`${userId}__${serviceLineId}`] !== true,
    [assignedByPair],
  );

  // Distinguishes *why* a cell is read-only, using only the project_status
  // already sent on every row, not a full reason taxonomy (that would also
  // need the service line's own active flag and a real "never assigned at all"
  // signal, neither of which is sent today): when the project itself isn't
  // active, that's almost certainly the actual cause, and saying so beats
  // always claiming the consultant was personally removed, which often isn't
  // true (e.g. a freshly Duplicated project, still Draft, with every
  // assignment copied over verbatim). Falls back to the original generic
  // message when the project *is* active, that's the one case this can't
  // disambiguate further without backend changes (service line deactivated vs.
  // genuinely never assigned).
  const unassignedTooltip = useCallback(
    (userId: string, serviceLineId: string) => {
      const status = projectStatusByPair[`${userId}__${serviceLineId}`];
      if (status === "draft") {
        return t("This service line is read-only because the project is still in Draft.");
      }
      if (status === "closed") {
        return t("This service line is read-only because the project has been closed.");
      }
      return t("This consultant is no longer assigned to this service line — read-only.");
    },
    [projectStatusByPair, t],
  );

  const isFullyLockedInPeriod = useCallback(
    (userId: string, serviceLineId: string) =>
      days.every(
        (day) => entries[cellKey(userId, serviceLineId, toDayKey(day))]?.is_locked === true,
      ),
    [days, entries],
  );

  const dayTotal = useCallback(
    (dayKey: string) =>
      sumHours(
        serviceLines.map((line) => entries[cellKey(line.user_id, line.service_line_id, dayKey)]?.hours),
      ),
    [serviceLines, entries],
  );

  const serviceLineTotal = useCallback(
    (userId: string, serviceLineId: string) =>
      sumHours(days.map((day) => entries[cellKey(userId, serviceLineId, toDayKey(day))]?.hours)),
    [days, entries],
  );

  const periodTotal = useMemo(
    () =>
      serviceLines.reduce(
        (sum, line) => sum + serviceLineTotal(line.user_id, line.service_line_id),
        0,
      ),
    [serviceLines, serviceLineTotal],
  );

  function handleCellChange(userId: string, serviceLineId: string, dayKey: string, value: string) {
    const key = cellKey(userId, serviceLineId, dayKey);
    setEntries((prev) => ({
      ...prev,
      [key]: { hours: value, is_locked: prev[key]?.is_locked ?? false },
    }));
  }

  async function handleCellBlur(userId: string, serviceLineId: string, dayKey: string) {
    const key = cellKey(userId, serviceLineId, dayKey);
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
      // Always an array, per the bulk endpoint's contract, and always an
      // explicit user_id here, never omitted: Reporting never edits an implicit
      // "caller's own" entry the way My Timesheet does, every row has a known
      // owner.
      const [result] = await upsertTimeEntries([
        { service_line_id: serviceLineId, date: dayKey, hours: corrected, user_id: userId },
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

  async function handleToggleLock(userId: string, serviceLineId: string) {
    const nextLocked = !isFullyLockedInPeriod(userId, serviceLineId);
    try {
      const updated = await setServiceLineLock({
        user_id: userId,
        service_line_id: serviceLineId,
        start_date: toDayKey(days[0]),
        end_date: toDayKey(days[days.length - 1]),
        locked: nextLocked,
      });
      setEntries((prev) => {
        const next = { ...prev };
        const updatedByDate = new Map(updated.map((entry) => [entry.date, entry]));
        for (const day of days) {
          const dayKey = toDayKey(day);
          const key = cellKey(userId, serviceLineId, dayKey);
          const entry = updatedByDate.get(dayKey);
          if (entry) {
            next[key] = { hours: formatHours(Number(entry.hours)), is_locked: entry.is_locked };
          } else if (!nextLocked) {
            // Unlock deleted this gap-day row (it had no real hours): same as
            // useTimesheetGrid's applyLockResult.
            delete next[key];
          }
        }
        return next;
      });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to update lock state."));
    }
  }

  return {
    entries,
    serviceLines,
    isUnassignedInPeriod,
    unassignedTooltip,
    isFullyLockedInPeriod,
    dayTotal,
    serviceLineTotal,
    periodTotal,
    handleCellChange,
    handleCellBlur,
    handleToggleLock,
  };
}
