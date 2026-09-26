import type { Column, RowData } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { features } from "@/components/data-table/features";

// Fixed to this app's one shared `features` registration: see DataTable.tsx's own
// comment for why a second TFeatures generic isn't worth carrying here.
interface DataTableColumnHeaderProps<TData extends RowData, TValue> {
  column: Column<typeof features, TData, TValue>;
  title: string;
  className?: string;
}

// Reusable sortable-column-header cell, shared by every shadcn/ui Data Table in this
// app. Clicking the header directly toggles ascending/descending, no intermediate
// menu, matching the convention most data tables use (this app's own first pass
// used a Asc/Desc/Hide dropdown per shadcn's template example, but that's not the
// common pattern and added an unnecessary click; column-hiding, where a table has
// any, stays reachable via that table's own toolbar "Columns" button instead). A
// column with no sorting enabled renders as a plain label; a sortable one shows the
// current direction (`ArrowUp`/`ArrowDown`) or `ChevronsUpDown` when unsorted. This
// is template/example code per shadcn's own docs (there's no `npx shadcn add` entry
// for it), so it lives under components/data-table/ rather than components/ui/.
export function DataTableColumnHeader<TData extends RowData, TValue>({
  column,
  title,
  className,
}: DataTableColumnHeaderProps<TData, TValue>) {
  if (!column.getCanSort()) {
    return <div className={className}>{title}</div>;
  }

  const sorted = column.getIsSorted();

  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn("-ml-3 h-8", className)}
      onClick={() => column.toggleSorting(sorted === "asc")}
    >
      <span>{title}</span>
      {sorted === "desc" ? (
        <ArrowDown className="ml-2 h-4 w-4" aria-hidden="true" />
      ) : sorted === "asc" ? (
        <ArrowUp className="ml-2 h-4 w-4" aria-hidden="true" />
      ) : (
        <ChevronsUpDown className="ml-2 h-4 w-4" aria-hidden="true" />
      )}
    </Button>
  );
}
