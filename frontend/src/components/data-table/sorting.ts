import type { SortingState } from "@tanstack/react-table";

/**
 * Translates TanStack's `SortingState` (empty when unsorted, else a single
 * `{id, desc}` entry per column since none of this app's tables use
 * multi-column sort) into the `sort_by`/`sort_dir` query params every list
 * endpoint expects: sorting is server-side (see each table's own `manualSorting:
 * true`), never a client-side `getSortedRowModel()`, since these tables are also
 * server-paginated: sorting only whatever page happens to already be in memory
 * doesn't produce a correct order across the whole (unloaded) dataset.
 */
export function toSortParams(
  sorting: SortingState,
): { sort_by?: string; sort_dir?: "asc" | "desc" } {
  const [first] = sorting;
  if (!first) return {};
  return { sort_by: first.id, sort_dir: first.desc ? "desc" : "asc" };
}
