import { Download, NotebookTabs, NotebookText, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  exportTimesheetReport,
  getReportFilters,
  getTimesheetReport,
  type TimesheetReportExportFormat,
} from "@/api/timeEntries";
import {
  FiletypeCsvIcon,
  FiletypePdfIcon,
  FiletypeXlsxIcon,
} from "@/components/reporting/ExportFormatIcons";
import { MineOnlySwitch } from "@/components/MineOnlySwitch";
import { ProjectStatusFilterDropdown } from "@/components/reporting/ProjectStatusFilterDropdown";
import { ReportFilterDropdown } from "@/components/reporting/ReportFilterDropdown";
import { TimesheetDesktopGrid } from "@/components/timesheet/TimesheetDesktopGrid";
import { TimesheetHeader } from "@/components/timesheet/TimesheetHeader";
import { TimesheetMobileView } from "@/components/timesheet/TimesheetMobileView";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { useReportGrid } from "@/hooks/useReportGrid";
import { downloadBlob } from "@/lib/download";
import { pruneSelection } from "@/lib/reportFilters";
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
import type {
  PeriodType,
  TimesheetReportFilters,
  TimesheetReportRow,
} from "@/types/timesheet";

// Reporting screen: a manager's cross-consultant view over timesheets,
// filterable by Consultants/Projects/Service Lines/Project Status, built on the
// exact same shared grid mechanism My Timesheet uses (see
// useReportGrid's own comment for how it differs from useTimesheetGrid).
export function ReportingPage() {
  const { t } = useTranslation(["timesheet"]);

  const [periodType, setPeriodType] = useState<PeriodType>(defaultPeriodType);
  const [periodDate, setPeriodDate] = useState<Date>(defaultPeriodDate);
  const [selectedKey, setSelectedKey] = useState<string>(() => toDayKey(defaultPeriodDate()));

  const [filterOptions, setFilterOptions] = useState<TimesheetReportFilters | null>(null);
  // Every filter starts unchecked: unchecked/empty means unfiltered, not "show
  // nothing".
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [serviceLineIds, setServiceLineIds] = useState<string[]>([]);
  const [consultantIds, setConsultantIds] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);

  // "Only see my projects": on at every visit, never remembered. `requestedMineOnly`
  // is what the switch shows; `mineOnly` is what the rows and exports use, and only
  // catches up once the options for the new scope have arrived and the selection has
  // been pruned to them, so the rows are never fetched with the new scope and a
  // selection the new options no longer offer.
  const [requestedMineOnly, setRequestedMineOnly] = useState(true);
  const [mineOnly, setMineOnly] = useState(true);

  const [rows, setRows] = useState<TimesheetReportRow[]>([]);

  const days = useMemo(() => getPeriodDays(periodType, periodDate), [periodType, periodDate]);

  // Static, not period-scoped: fetched on mount and again for each switch toggle,
  // never on period or filter changes: each dropdown always lists the full set for
  // the chosen scope and is never narrowed by the other filters.
  useEffect(() => {
    // A quick double toggle can resolve out of order: only the latest request may
    // land.
    let stale = false;
    getReportFilters(requestedMineOnly)
      .then((options) => {
        if (stale) return;
        const pruned = pruneSelection({ projectIds, serviceLineIds, consultantIds }, options);
        setFilterOptions(options);
        setProjectIds(pruned.projectIds);
        setServiceLineIds(pruned.serviceLineIds);
        setConsultantIds(pruned.consultantIds);
        setMineOnly(requestedMineOnly);
      })
      .catch((err: unknown) => {
        if (stale) return;
        toast.error(err instanceof ApiError ? err.message : t("Failed to load filters."));
      });
    return () => {
      stale = true;
    };
    // Only a scope change refetches: the selection is read for pruning, not watched.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedMineOnly, t]);

  useEffect(() => {
    const start = toDayKey(days[0]);
    const end = toDayKey(days[days.length - 1]);
    getTimesheetReport({
      startDate: start,
      endDate: end,
      projectIds,
      serviceLineIds,
      consultantIds,
      statuses,
      mineOnly,
    })
      .then((res) => setRows(res.items))
      .catch((err: unknown) => {
        toast.error(err instanceof ApiError ? err.message : t("Failed to load timesheets."));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    periodType,
    periodDate,
    projectIds,
    serviceLineIds,
    consultantIds,
    statuses,
    mineOnly,
    t,
  ]);

  const {
    entries,
    serviceLines,
    isUnassignedInPeriod,
    unassignedTooltip,
    isFullyLockedInPeriod,
    dayTotal,
    serviceLineTotal,
    periodTotal,
    handleCellChange,
    handleCellFocus,
    handleCellBlur,
    handleToggleLock,
  } = useReportGrid({ days, rows });

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

  const [exportingFormat, setExportingFormat] = useState<TimesheetReportExportFormat | null>(
    null,
  );

  // Always re-queries fresh server-side with the exact same filters this
  // screen is currently showing, so the export can never diverge from the
  // on-screen view.
  async function handleExport(format: TimesheetReportExportFormat) {
    setExportingFormat(format);
    try {
      const { blob, filename } = await exportTimesheetReport(format, {
        startDate: toDayKey(days[0]),
        endDate: toDayKey(days[days.length - 1]),
        periodType,
        projectIds,
        serviceLineIds,
        consultantIds,
        statuses,
        mineOnly,
      });
      downloadBlob(blob, filename ?? `timesheet-report.${format}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : t("Failed to export."));
    } finally {
      setExportingFormat(null);
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

      <Separator />

      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-sm font-semibold">{t("Filters")}</span>
          <ReportFilterDropdown
            label={t("Consultants")}
            icon={UsersRound}
            options={(filterOptions?.consultants ?? []).map((c) => ({
              id: c.user_id,
              label: c.full_name,
            }))}
            selected={consultantIds}
            onChange={setConsultantIds}
          />
          <ReportFilterDropdown
            label={t("Projects")}
            icon={NotebookTabs}
            options={(filterOptions?.projects ?? []).map((p) => ({
              id: p.project_id,
              label: p.name,
            }))}
            selected={projectIds}
            onChange={setProjectIds}
          />
          <ReportFilterDropdown
            label={t("Service Lines")}
            icon={NotebookText}
            options={(filterOptions?.service_lines ?? []).map((l) => ({
              id: l.service_line_id,
              label: l.service_line_name
                ? `${l.project_name} — ${l.service_line_name}`
                : l.project_name,
            }))}
            selected={serviceLineIds}
            onChange={setServiceLineIds}
          />
          <ProjectStatusFilterDropdown selected={statuses} onChange={setStatuses} />
          <MineOnlySwitch checked={requestedMineOnly} onCheckedChange={setRequestedMineOnly} />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              className="gap-2"
              disabled={exportingFormat !== null}
            >
              {exportingFormat ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <Download className="h-4 w-4" aria-hidden="true" />
              )}
              {exportingFormat ? t("Exporting…") : t("Export")}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => void handleExport("pdf")}>
              <FiletypePdfIcon className="mr-2 h-4 w-4" />
              {t("Export as PDF")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleExport("xlsx")}>
              <FiletypeXlsxIcon className="mr-2 h-4 w-4" />
              {t("Export as Excel")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => void handleExport("csv")}>
              <FiletypeCsvIcon className="mr-2 h-4 w-4" />
              {t("Export as CSV")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Separator />

      {rows.length === 0 && (
        <p className="text-muted-foreground p-4 text-sm">
          {t("No timesheets match the current filters.")}
        </p>
      )}

      <TimesheetMobileView
        days={days}
        selectedKey={selectedKey}
        onSelectDay={setSelectedKey}
        serviceLines={serviceLines}
        entries={entries}
        showSummaryFooter={false}
        periodLabel={periodLabel}
        isUnassignedInPeriod={isUnassignedInPeriod}
        unassignedTooltip={unassignedTooltip}
        onCellChange={handleCellChange}
        onCellFocus={handleCellFocus}
        onCellBlur={handleCellBlur}
        dayTotal={dayTotal}
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
        isUnassignedInPeriod={isUnassignedInPeriod}
        unassignedTooltip={unassignedTooltip}
        onCellChange={handleCellChange}
        onCellFocus={handleCellFocus}
        onCellBlur={handleCellBlur}
        onFocusDay={setSelectedKey}
        isFullyLockedInPeriod={isFullyLockedInPeriod}
        onToggleLock={handleToggleLock}
      />
    </div>
  );
}
