import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { EligibleServiceLine } from "@/types/timesheet";

interface AddServiceLineSelectProps {
  options: EligibleServiceLine[];
  onAdd: (serviceLineId: string) => void;
}

export function AddServiceLineSelect({ options, onAdd }: AddServiceLineSelectProps) {
  const { t } = useTranslation(["timesheet"]);

  if (options.length === 0) return null;

  return (
    <Select value="" onValueChange={onAdd}>
      <SelectTrigger className="w-full sm:w-80">
        <Plus className="mr-1 h-4 w-4 shrink-0" aria-hidden="true" />
        <SelectValue placeholder={t("Add service line")} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.service_line_id} value={option.service_line_id}>
            {option.project_name}
            {option.service_line_name ? ` — ${option.service_line_name}` : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
