import {
  useTable,
  type ColumnDef,
  type OnChangeFn,
  type SortingState,
  type ColumnVisibilityState,
} from "@tanstack/react-table";
import { Columns3, MoreHorizontal, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
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
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
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
import { deactivateProject, duplicateProject, listProjects } from "@/api/projects";
import { PROJECT_TYPE_LABELS, STATUS_LABELS, type ProjectListItem } from "@/types/project";

const SEARCH_DEBOUNCE_MS = 300;

const STATUS_BADGE_VARIANT: Record<ProjectListItem["status"], BadgeProps["variant"]> = {
  draft: "secondary",
  active: "default",
  closed: "outline",
};

// Labels for the "Columns" visibility dropdown: keyed by column id, kept separate from
// the columns' own `header` (which is only rendered when the column is visible).
const HIDEABLE_COLUMN_LABELS: Record<string, string> = {
  vendor_company_name: "Vendor",
};

export function ProjectsTable() {
  const navigate = useNavigate();
  const { t } = useTranslation(["projects", "common"]);

  const [items, setItems] = useState<ProjectListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  // vendor_company_name is opt-in via the "Columns" button: hidden by default.
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    vendor_company_name: false,
  });
  // Sorting is server-side (see the `manualSorting: true` below and
  // components/data-table/sorting.ts): this table is also server-paginated, so a
  // client-side-only sort would only ever reorder whatever page is already in
  // memory, not the whole dataset.
  const [sorting, setSorting] = useState<SortingState>([]);

  // A changed sort target/direction changes what "page 1" even means: same reasoning as the
  // search-resets-page-to-1 reset above. Done in the change handler, not an effect, so the new
  // sort and page 1 land in one render and no request is made with the new sort and the old page.
  const handleSortingChange: OnChangeFn<SortingState> = (updater) => {
    setSorting(updater);
    setPage(1);
  };

  useEffect(() => {
    const handle = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    listProjects({ search: search || undefined, page, ...toSortParams(sorting) })
      .then((response) => {
        if (cancelled) return;
        setError(null);
        setItems(response.items);
        setTotal(response.total);
        setPageSize(response.page_size);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : t("Failed to load projects."));
      });
    return () => {
      cancelled = true;
    };
  }, [search, page, sorting, refreshToken, t]);

  async function handleDuplicate(project: ProjectListItem) {
    try {
      const duplicated = await duplicateProject(project.id);
      toast.success(t("{{name}} duplicated.", { name: project.name }));
      navigate(`/projects/${duplicated.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to duplicate project."));
    }
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deactivateProject(deleteTarget.id);
      toast.success(t("{{name}} deleted.", { name: deleteTarget.name }));
      setDeleteTarget(null);
      setRefreshToken((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete project."));
    } finally {
      setIsDeleting(false);
    }
  }

  const columns: ColumnDef<typeof features, ProjectListItem>[] = [
    {
      accessorKey: "name",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Name")} />,
      enableHiding: false,
    },
    {
      accessorKey: "status",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Status")} />,
      enableHiding: false,
      cell: ({ row }) => (
        <Badge variant={STATUS_BADGE_VARIANT[row.original.status]}>
          {t(STATUS_LABELS[row.original.status])}
        </Badge>
      ),
    },
    {
      accessorKey: "client_company_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Client")} />,
      enableHiding: false,
      cell: ({ row }) => row.original.client_company_name ?? "—",
    },
    {
      accessorKey: "vendor_company_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Vendor")} />,
      enableHiding: true,
      cell: ({ row }) => row.original.vendor_company_name ?? "—",
    },
    {
      accessorKey: "project_type",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("Project Type")} />
      ),
      enableHiding: false,
      cell: ({ row }) => t(PROJECT_TYPE_LABELS[row.original.project_type]),
    },
    {
      accessorKey: "created_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("Creation Date")} />
      ),
      enableHiding: false,
      cell: ({ row }) => new Date(row.original.created_at).toLocaleDateString(),
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
              <DropdownMenuItem onClick={() => navigate(`/projects/${row.original.id}`)}>
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
    // No columnFilteringFeature registered: search is entirely custom (a debounced
    // server-side query, not TanStack's own filter row-model), so there's no
    // `manualFiltering` flag to set: that option only exists as part of
    // columnFilteringFeature, which this app never uses.
    manualPagination: true,
    // `data` already arrives sorted from the server (see the fetch effect above):
    // no sortedRowModel slot on `features`, it would only ever reorder this one
    // page in memory.
    manualSorting: true,
    pageCount: Math.max(1, Math.ceil(total / pageSize)),
    state: { columnVisibility, sorting },
    onColumnVisibilityChange: setColumnVisibility,
    onSortingChange: handleSortingChange,
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Input
          placeholder={t("Search by name…")}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-sm"
        />
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Columns3 className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("Columns", { ns: "common" })}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {table
                .getAllColumns()
                .filter((column) => column.getCanHide())
                .map((column) => (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    checked={column.getIsVisible()}
                    onCheckedChange={(checked) => column.toggleVisibility(!!checked)}
                    onSelect={(e) => e.preventDefault()}
                  >
                    {t(HIDEABLE_COLUMN_LABELS[column.id] ?? column.id)}
                  </DropdownMenuCheckboxItem>
                ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button onClick={() => navigate("/projects/new")}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("New", { ns: "common" })}
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <DataTable
        table={table}
        columnCount={columns.length}
        emptyMessage={t("No projects found.")}
      />

      <DataTablePagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        countLabel={t("projectCount", { count: total })}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("Delete {{name}}?", { name: deleteTarget?.name })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "This deactivates the project (it can't be reactivated from the UI currently) and removes it from this list.",
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
