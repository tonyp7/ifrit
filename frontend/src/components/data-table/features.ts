import {
  columnVisibilityFeature,
  rowPaginationFeature,
  rowSortingFeature,
  tableFeatures,
} from "@tanstack/react-table";

// Every Data Table in this app registers the same three features: sorting and
// pagination (every table: see the `manualSorting`/`manualPagination` note
// below) and column visibility (only Projects' "Vendor" column uses it today,
// via the "Columns" toolbar button: registering it for every table anyway
// keeps one shared object instead of per-table variants, at negligible cost
// for an internal admin app this size). No `columnFilteringFeature`: search is
// entirely custom (a debounced server-side query), never TanStack's own
// filter row-model, so there's no corresponding feature to register at all.
//
// Deliberately no row-model slot for sorting or pagination (no `sortedRowModel`/
// `paginatedRowModel`): every table sets `manualSorting`/`manualPagination`, so
// the server has already sorted and paginated `data` before it reaches the
// table: there's nothing left for a client-side row model to compute; the
// feature is registered purely for its column/table APIs and state
// (`column.toggleSorting`, `state.pagination`, etc.), matching TanStack's own
// "server owns processing" pattern for manual features.
export const features = tableFeatures({
  rowSortingFeature,
  rowPaginationFeature,
  columnVisibilityFeature,
});
