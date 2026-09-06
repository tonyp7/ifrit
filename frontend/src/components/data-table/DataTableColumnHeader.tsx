import type { Column } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface DataTableColumnHeaderProps<TData, TValue> {
  column: Column<TData, TValue>;
  title: string;
  className?: string;
}

// Reusable sortable-column-header cell, shared by every shadcn/ui Data Table in this
// app — adapted from shadcn's own `components/data-table-column-header.tsx` template
// (https://ui.shadcn.com/docs/components/aria/data-table): a column with no sorting
// enabled renders as a plain label; a sortable one becomes a dropdown trigger showing
// the current direction (`ArrowUp`/`ArrowDown`) or `ChevronsUpDown` when unsorted, with
// Asc/Desc/Hide actions. This is template/example code per shadcn's own docs (there's
// no `npx shadcn add` entry for it), so it lives under components/data-table/ rather
// than components/ui/ — see docs/architecture/frontend.md#file-organization's
// distinction between shadcn/ui primitives and feature-specific components.
export function DataTableColumnHeader<TData, TValue>({
  column,
  title,
  className,
}: DataTableColumnHeaderProps<TData, TValue>) {
  const { t } = useTranslation(["common"]);

  if (!column.getCanSort()) {
    return <div className={className}>{title}</div>;
  }

  const sorted = column.getIsSorted();

  return (
    <div className={cn("flex items-center", className)}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="-ml-3 h-8 data-[state=open]:bg-secondary">
            <span>{title}</span>
            {sorted === "desc" ? (
              <ArrowDown className="ml-2 h-4 w-4" aria-hidden="true" />
            ) : sorted === "asc" ? (
              <ArrowUp className="ml-2 h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronsUpDown className="ml-2 h-4 w-4" aria-hidden="true" />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onClick={() => column.toggleSorting(false)}>
            <ArrowUp className="mr-2 h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            {t("Ascending")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => column.toggleSorting(true)}>
            <ArrowDown className="mr-2 h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            {t("Descending")}
          </DropdownMenuItem>
          {column.getCanHide() && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => column.toggleVisibility(false)}>
                <EyeOff className="mr-2 h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                {t("Hide column")}
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
