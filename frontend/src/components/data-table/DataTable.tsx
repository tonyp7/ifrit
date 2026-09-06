import { flexRender, type RowData, type Table as TableInstance } from "@tanstack/react-table";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { features } from "@/components/data-table/features";

// Fixed to this app's one shared `features` registration (see features.ts) rather
// than staying generic over an arbitrary TFeatures — there's only ever one
// instantiation in this codebase, so a second generic param here would be
// complexity with no actual payoff.
interface DataTableProps<TData extends RowData> {
  table: TableInstance<typeof features, TData>;
  /** Total column count, for the empty-state row's colSpan. */
  columnCount: number;
  emptyMessage: string;
}

// Shared table-shell markup (header groups, body rows, empty state) for every
// shadcn/ui Data Table in this app — the caller still owns its own `useTable()` call
// (column defs, sorting/visibility state) since that differs per table; this only
// removes the ~25 duplicated lines of render JSX every list screen otherwise repeats
// verbatim. See components/data-table/DataTableColumnHeader.tsx's own comment for why
// this lives here rather than under components/ui/.
export function DataTable<TData extends RowData>({
  table,
  columnCount,
  emptyMessage,
}: DataTableProps<TData>) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columnCount} className="h-24 text-center">
                {emptyMessage}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
