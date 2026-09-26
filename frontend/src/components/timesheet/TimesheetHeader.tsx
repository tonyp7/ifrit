import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatMonthLabel, getIsoWeekNumber } from "@/lib/timesheetDates";
import { formatHours } from "@/lib/timesheetHours";
import type { PeriodType } from "@/types/timesheet";

interface TimesheetHeaderProps {
  periodType: PeriodType;
  periodDate: Date;
  periodTotal: number;
  onPeriodTypeChange: (next: PeriodType) => void;
  onNavigate: (direction: 1 | -1) => void;
}

export function TimesheetHeader({
  periodType,
  periodDate,
  periodTotal,
  onPeriodTypeChange,
  onNavigate,
}: TimesheetHeaderProps) {
  const { t } = useTranslation(["timesheet"]);

  const label =
    periodType === "month"
      ? formatMonthLabel(periodDate)
      : t("Week {{number}}", { number: getIsoWeekNumber(periodDate) });

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
      <Tabs
        value={periodType}
        onValueChange={(value) => onPeriodTypeChange(value as PeriodType)}
      >
        <TabsList>
          <TabsTrigger value="week">{t("Week")}</TabsTrigger>
          <TabsTrigger value="month">{t("Month")}</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label={t("Previous", { ns: "common" })}
          onClick={() => onNavigate(-1)}
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </Button>
        <span className="min-w-32 text-center text-sm font-medium">{label}</span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label={t("Next", { ns: "common" })}
          onClick={() => onNavigate(1)}
        >
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>

      <div className="text-sm font-semibold">
        {t("Total")}: {formatHours(periodTotal) || "0"}h
      </div>
    </div>
  );
}
