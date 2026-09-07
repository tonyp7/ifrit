import {
  useTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { MoreHorizontal, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { DataTable } from "@/components/data-table/DataTable";
import { DataTableColumnHeader } from "@/components/data-table/DataTableColumnHeader";
import { DataTablePagination } from "@/components/data-table/DataTablePagination";
import { features } from "@/components/data-table/features";
import { toSortParams } from "@/components/data-table/sorting";
import { ApiError } from "@/api/client";
import { deactivateCompany, duplicateCompany, listCompanies } from "@/api/companies";
import type { CompanyListItem } from "@/types/company";

const SEARCH_DEBOUNCE_MS = 300;

export function CompaniesTable() {
  const navigate = useNavigate();
  const { t } = useTranslation(["company", "common"]);

  const [items, setItems] = useState<CompanyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<CompanyListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  // Sorting is server-side (see the `manualSorting: true` below and
  // components/data-table/sorting.ts) — this table is also server-paginated, so a
  // client-side-only sort would only ever reorder whatever page is already in
  // memory, not the whole dataset (see specs/requirements/company.md
  // #companies-list-screen).
  const [sorting, setSorting] = useState<SortingState>([]);

  // Debounce the search input before it drives the actual (server-side) filter —
  // shadcn/ui's native Data Table filter component, kept manual/server-driven rather
  // than tanstack's client-side row filtering, since results are paginated server-side
  // (see specs/requirements/company.md#companies-list-screen).
  useEffect(() => {
    const handle = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInput]);

  // A changed sort target/direction changes what "page 1" even means — same
  // reasoning as the search-resets-page-to-1 effect above.
  useEffect(() => {
    setPage(1);
  }, [sorting]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    listCompanies({ search: search || undefined, page, ...toSortParams(sorting) })
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
        setTotal(response.total);
        setPageSize(response.page_size);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : t("Failed to load companies."));
      });
    return () => {
      cancelled = true;
    };
  }, [search, page, sorting, refreshToken, t]);

  async function handleDuplicate(company: CompanyListItem) {
    try {
      const duplicated = await duplicateCompany(company.id);
      toast.success(t("{{name}} duplicated.", { name: company.legal_name }));
      navigate(`/configuration/companies/${duplicated.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to duplicate company."));
    }
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deactivateCompany(deleteTarget.id);
      toast.success(t("{{name}} deleted.", { name: deleteTarget.legal_name }));
      setDeleteTarget(null);
      setRefreshToken((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete company."));
    } finally {
      setIsDeleting(false);
    }
  }

  const columns: ColumnDef<typeof features, CompanyListItem>[] = [
    {
      accessorKey: "legal_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Legal name")} />,
      enableHiding: false,
    },
    {
      accessorKey: "country_of_registration",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Country")} />,
      enableHiding: false,
    },
    {
      accessorKey: "is_active",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Status")} />,
      enableHiding: false,
      cell: ({ row }) => (
        <Badge variant={row.original.is_active ? "default" : "secondary"}>
          {row.original.is_active ? t("Active", { ns: "common" }) : t("Inactive", { ns: "common" })}
        </Badge>
      ),
    },
    {
      id: "actions",
      header: "",
      enableHiding: false,
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">{t("Actions", { ns: "common" })}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() =>
                  navigate(`/configuration/companies/${row.original.id}`)
                }
              >
                {t("Edit", { ns: "common" })}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => void handleDuplicate(row.original)}>
                {t("Duplicate", { ns: "common" })}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => setDeleteTarget(row.original)}
              >
                {t("Delete", { ns: "common" })}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
    },
  ];

  const table = useTable({
    features,
    data: items,
    columns,
    // No columnFilteringFeature registered — search is entirely custom (a debounced
    // server-side query, not TanStack's own filter row-model), so there's no
    // `manualFiltering` flag to set: that option only exists as part of
    // columnFilteringFeature, which this app never uses.
    manualPagination: true,
    // `data` already arrives sorted from the server (see the fetch effect above) —
    // no sortedRowModel slot on `features`, it would only ever reorder this one
    // page in memory.
    manualSorting: true,
    pageCount: Math.max(1, Math.ceil(total / pageSize)),
    state: { sorting },
    onSortingChange: setSorting,
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Input
          placeholder={t("Search by legal name…")}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-sm"
        />
        <Button onClick={() => navigate("/configuration/companies/new")}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("New", { ns: "common" })}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <DataTable
        table={table}
        columnCount={columns.length}
        emptyMessage={t("No companies found.")}
      />

      <DataTablePagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        countLabel={t("companyCount", { count: total })}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("Delete {{name}}?", { name: deleteTarget?.legal_name })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "This deactivates the company (it can't be reactivated from the UI currently). It will no longer be selectable for new projects.",
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>
              {t("Cancel", { ns: "common" })}
            </AlertDialogCancel>
            <AlertDialogAction disabled={isDeleting} onClick={() => void handleConfirmDelete()}>
              {isDeleting && <Spinner />}
              {isDeleting ? t("Deleting…", { ns: "common" }) : t("Delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
