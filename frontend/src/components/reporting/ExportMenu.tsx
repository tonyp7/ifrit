import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  TimesheetReportExportFormat,
  TimesheetReportExportUnit,
} from "@/api/timeEntries";
import {
  FiletypeCsvIcon,
  FiletypePdfIcon,
  FiletypeXlsxIcon,
} from "@/components/reporting/ExportFormatIcons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";

interface ExportMenuProps {
  // The format being exported right now, or null; the whole control is disabled meanwhile.
  exportingFormat: TimesheetReportExportFormat | null;
  onExport: (format: TimesheetReportExportFormat, unit: TimesheetReportExportUnit) => void;
}

// The Reporting screen's Export button: a format per item, then the unit the file counts in.
// The unit is plain state that starts at hours each time the screen opens, on purpose: hours is
// the default, and a remembered "days" would silently change the next export.
export function ExportMenu({ exportingFormat, onExport }: ExportMenuProps) {
  const { t } = useTranslation(["timesheet"]);
  const [unit, setUnit] = useState<TimesheetReportExportUnit>("hours");

  return (
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
        <DropdownMenuItem onClick={() => onExport("pdf", unit)}>
          <FiletypePdfIcon className="mr-2 h-4 w-4" />
          {t("Export as PDF")}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onExport("xlsx", unit)}>
          <FiletypeXlsxIcon className="mr-2 h-4 w-4" />
          {t("Export as Excel")}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onExport("csv", unit)}>
          <FiletypeCsvIcon className="mr-2 h-4 w-4" />
          {t("Export as CSV")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t("Export as…")}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={unit}
          onValueChange={(value) => setUnit(value as TimesheetReportExportUnit)}
        >
          {/* Radix closes the menu on any selection; a unit is a setting, not an action, so
              keep it open (the value still changes). */}
          <DropdownMenuRadioItem value="hours" onSelect={(event) => event.preventDefault()}>
            {t("Hours")}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="days" onSelect={(event) => event.preventDefault()}>
            {t("Days")}
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
