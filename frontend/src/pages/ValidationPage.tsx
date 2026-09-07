import { Fragment, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { getManagedTimeEntries } from "@/api/timeEntries";
import { ConsultantTimesheetBlock } from "@/components/timesheet/ConsultantTimesheetBlock";
import { TimesheetHeader } from "@/components/timesheet/TimesheetHeader";
import { Separator } from "@/components/ui/separator";
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
import type { ManagedConsultant, PeriodType } from "@/types/timesheet";

// Validation screen (see specs/requirements/timesheet.md's Validation section) — a
// project_manager's review/edit/lock surface over consultants' timesheets. One
// shared header governs every consultant block below it at once (§Screen layout);
// each block is the exact same shared grid mechanism My Timesheet uses, via
// ConsultantTimesheetBlock, separated by a shadcn/ui Separator between (not
// before the first or after the last) blocks.
export function ValidationPage() {
  const { t } = useTranslation(["timesheet"]);

  const [periodType, setPeriodType] = useState<PeriodType>(defaultPeriodType);
  const [periodDate, setPeriodDate] = useState<Date>(defaultPeriodDate);
  const [selectedKey, setSelectedKey] = useState<string>(() => toDayKey(defaultPeriodDate()));
  const [consultants, setConsultants] = useState<ManagedConsultant[]>([]);

  const days = useMemo(() => getPeriodDays(periodType, periodDate), [periodType, periodDate]);

  useEffect(() => {
    const start = toDayKey(days[0]);
    const end = toDayKey(days[days.length - 1]);
    getManagedTimeEntries(start, end)
      .then((res) => {
        // Ascending by full_name — proposed order per specs/requirements/timesheet.md's
        // Validation § Screen layout.
        setConsultants([...res.consultants].sort((a, b) => a.full_name.localeCompare(b.full_name)));
      })
      .catch((err: unknown) => {
        toast.error(err instanceof ApiError ? err.message : t("Failed to load timesheets."));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodType, periodDate, t]);

  // Non-critical summary figure (same spirit as My Timesheet's monthToDateTotal) —
  // a snapshot from the last load, not live-recomputed from every block's local
  // edits; not specified by the doc, just a reasonable use of the Shared Header's
  // existing "Total" slot rather than leaving it blank.
  const periodTotal = useMemo(
    () => sumHours(consultants.flatMap((c) => c.entries.map((entry) => entry.hours))),
    [consultants],
  );

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

      {consultants.length === 0 && (
        <p className="p-4 text-sm text-muted-foreground">
          {t("No consultants to review for this period.")}
        </p>
      )}

      {consultants.map((consultant, index) => (
        <Fragment key={consultant.user_id}>
          {index > 0 && <Separator />}
          <ConsultantTimesheetBlock
            consultant={consultant}
            periodType={periodType}
            days={days}
            periodLabel={periodLabel}
            selectedKey={selectedKey}
            onSelectDay={setSelectedKey}
          />
        </Fragment>
      ))}
    </div>
  );
}
