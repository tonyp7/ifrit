import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { setServiceLineLock } from "@/api/timeEntries";
import { TimesheetDesktopGrid } from "@/components/timesheet/TimesheetDesktopGrid";
import { TimesheetMobileView } from "@/components/timesheet/TimesheetMobileView";
import { useTimesheetGrid } from "@/hooks/useTimesheetGrid";
import { toDayKey } from "@/lib/timesheetDates";
import type { ManagedConsultant, PeriodType } from "@/types/timesheet";

interface ConsultantTimesheetBlockProps {
  consultant: ManagedConsultant;
  periodType: PeriodType;
  days: Date[];
  periodLabel: string;
  selectedKey: string;
  onSelectDay: (dayKey: string) => void;
}

// One block on the Validation screen (see specs/requirements/timesheet.md's
// Validation § Screen layout) — a bold consultant-name header plus that
// consultant's timesheet, rendered through the exact same shared grid components
// and useTimesheetGrid hook My Timesheet uses (see the Validation "Implementation
// note: one shared mechanism, not two"), parameterized with this consultant's
// user_id as the override owner and a lock control on each row.
export function ConsultantTimesheetBlock({
  consultant,
  periodType,
  days,
  periodLabel,
  selectedKey,
  onSelectDay,
}: ConsultantTimesheetBlockProps) {
  const { t } = useTranslation(["timesheet"]);

  const {
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
  } = useTimesheetGrid({
    days,
    initialEntries: consultant.entries,
    eligibleLines: consultant.eligible_service_lines,
    ownerUserId: consultant.user_id,
  });

  async function handleToggleLock(serviceLineId: string) {
    const nextLocked = !isFullyLockedInPeriod(serviceLineId);
    try {
      const updated = await setServiceLineLock({
        user_id: consultant.user_id,
        service_line_id: serviceLineId,
        start_date: toDayKey(days[0]),
        end_date: toDayKey(days[days.length - 1]),
        locked: nextLocked,
      });
      applyLockResult(serviceLineId, updated, nextLocked);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to update lock state."));
    }
  }

  return (
    <div className="flex flex-col">
      <h2 className="px-4 pt-4 text-base font-bold">{consultant.full_name}</h2>

      <TimesheetMobileView
        days={days}
        selectedKey={selectedKey}
        onSelectDay={onSelectDay}
        serviceLines={serviceLines}
        entries={entries}
        dayTotal={dayTotal}
        showSummaryFooter={false}
        periodLabel={periodLabel}
        addOptions={addOptions}
        onAddServiceLine={handleAddServiceLine}
        hasEntriesInPeriod={hasEntriesInPeriod}
        hasLockedEntriesInPeriod={hasLockedEntriesInPeriod}
        isUnassignedInPeriod={isUnassignedInPeriod}
        onRemoveServiceLine={handleRemoveServiceLine}
        onClearAndRemoveServiceLine={handleClearAndRemoveServiceLine}
        onCellChange={handleCellChange}
        onCellBlur={handleCellBlur}
        isFullyLockedInPeriod={isFullyLockedInPeriod}
        onToggleLock={handleToggleLock}
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
        onCellBlur={handleCellBlur}
        onFocusDay={onSelectDay}
        isFullyLockedInPeriod={isFullyLockedInPeriod}
        onToggleLock={handleToggleLock}
      />
    </div>
  );
}
