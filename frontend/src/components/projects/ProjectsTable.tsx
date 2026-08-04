import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type VisibilityState,
} from "@tanstack/react-table";
import { Columns3, MoreHorizontal, Plus } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/api/client";
import { deactivateProject, duplicateProject, listProjects } from "@/api/projects";
import { PROJECT_TYPE_LABELS, STATUS_LABELS, type ProjectListItem } from "@/types/project";

const SEARCH_DEBOUNCE_MS = 300;

const STATUS_BADGE_VARIANT: Record<ProjectListItem["status"], BadgeProps["variant"]> = {
  draft: "secondary",
  active: "default",
  closed: "outline",
};

// Labels for the "Columns" visibility dropdown — keyed by column id, kept separate from
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
  // vendor_company_name is opt-in via the "Columns" button (see
  // docs/requirements/project.md#projects-list-screen) — hidden by default.
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({
    vendor_company_name: false,
  });

  useEffect(() => {
    const handle = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    listProjects({ search: search || undefined, page })
      .then((response) => {
        if (cancelled) return;
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
  }, [search, page, refreshToken, t]);

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

  const columns: ColumnDef<ProjectListItem>[] = [
    {
      accessorKey: "name",
      header: t("Name"),
    },
    {
      accessorKey: "status",
      header: t("Status"),
      cell: ({ row }) => (
        <Badge variant={STATUS_BADGE_VARIANT[row.original.status]}>
          {t(STATUS_LABELS[row.original.status])}
        </Badge>
      ),
    },
    {
      accessorKey: "client_company_name",
      header: t("Client"),
    },
    {
      accessorKey: "vendor_company_name",
      header: t("Vendor"),
      enableHiding: true,
    },
    {
      accessorKey: "project_type",
      header: t("Project Type"),
      cell: ({ row }) => t(PROJECT_TYPE_LABELS[row.original.project_type]),
    },
    {
      accessorKey: "created_at",
      header: t("Creation Date"),
      cell: ({ row }) => new Date(row.original.created_at).toLocaleDateString(),
    },
    {
      id: "actions",
      header: "",
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

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualFiltering: true,
    manualPagination: true,
    pageCount: Math.max(1, Math.ceil(total / pageSize)),
    state: { columnVisibility },
    onColumnVisibilityChange: setColumnVisibility,
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
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  {t("No projects found.")}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {t("projectCount", { count: total })}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            {t("Previous", { ns: "common" })}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p + 1)}
            disabled={page * pageSize >= total}
          >
            {t("Next", { ns: "common" })}
          </Button>
        </div>
      </div>

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
              {t("Delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
