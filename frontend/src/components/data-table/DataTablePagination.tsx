import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

interface DataTablePaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  /** e.g. t("projectCount", { count: total }) — pluralization differs per table's
   * own i18next namespace, so the caller supplies the already-translated label. */
  countLabel: string;
}

// Shared Previous/Next footer — every list screen in this app paginates the same way
// (50/page, server-side, no jump-to-page — see e.g.
// specs/requirements/company.md#companies-list-screen), so this was identical
// boilerplate across every table already; see DataTable.tsx's own comment for why
// this lives under components/data-table/ rather than components/ui/.
export function DataTablePagination({
  page,
  pageSize,
  total,
  onPageChange,
  countLabel,
}: DataTablePaginationProps) {
  const { t } = useTranslation(["common"]);

  return (
    <div className="flex items-center justify-between">
      <p className="text-sm text-muted-foreground">{countLabel}</p>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
        >
          {t("Previous")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page * pageSize >= total}
        >
          {t("Next")}
        </Button>
      </div>
    </div>
  );
}
