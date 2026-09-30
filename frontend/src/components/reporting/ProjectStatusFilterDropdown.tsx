import { ListFilter } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ReportFilterDropdown } from "@/components/reporting/ReportFilterDropdown";

interface ProjectStatusFilterDropdownProps {
  selected: string[];
  onChange: (next: string[]) => void;
}

// Thin wrapper around ReportFilterDropdown: same visual family as the other three
// filters, but a fixed 3-value list (draft/active/closed, the project Status enum)
// with no search bar: a search input over 3 items is pointless UI.
export function ProjectStatusFilterDropdown({
  selected,
  onChange,
}: ProjectStatusFilterDropdownProps) {
  const { t } = useTranslation(["timesheet"]);

  return (
    <ReportFilterDropdown
      label={t("Project Status")}
      icon={ListFilter}
      searchable={false}
      options={[
        { id: "draft", label: t("Draft") },
        { id: "active", label: t("Active") },
        { id: "closed", label: t("Closed") },
      ]}
      selected={selected}
      onChange={onChange}
    />
  );
}
