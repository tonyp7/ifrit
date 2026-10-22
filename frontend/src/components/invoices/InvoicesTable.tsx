import {
  useTable,
  type ColumnDef,
  type ColumnVisibilityState,
  type OnChangeFn,
  type SortingState,
} from "@tanstack/react-table";
import { Columns3, FolderKanban, ListFilter, MoreHorizontal, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  deleteInvoice,
  duplicateInvoice,
  listInvoiceProjects,
  listInvoices,
  downloadInvoicePdf,
} from "@/api/invoices";
import { DataTable } from "@/components/data-table/DataTable";
import { DataTableColumnHeader } from "@/components/data-table/DataTableColumnHeader";
import { DataTablePagination } from "@/components/data-table/DataTablePagination";
import { features } from "@/components/data-table/features";
import { RowLink } from "@/components/data-table/RowControl";
import { toSortParams } from "@/components/data-table/sorting";
import {
  ReportFilterDropdown,
  type ReportFilterOption,
} from "@/components/reporting/ReportFilterDropdown";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDueDate } from "@/lib/billingMilestones";
import { downloadBlob } from "@/lib/download";
import { formatMoney } from "@/lib/format";
import { canDownloadPdf } from "@/lib/invoicePdf";
import { formatPeriod } from "@/lib/invoicePeriods";
import { parseDayKey } from "@/lib/timesheetDates";
import {
  DEFAULT_STATUS_FILTER,
  INVOICE_STATUS_LABELS,
  INVOICE_STATUSES,
  PAYMENT_TERMS_LABELS,
  type InvoiceListItem,
  type InvoiceStatus,
} from "@/types/invoice";

const STATUS_BADGE_VARIANT: Record<InvoiceListItem["status"], BadgeProps["variant"]> = {
  draft: "secondary",
  issued: "default",
  void: "outline",
};

/** "1–30 Sep 2026" for an invoice with a period, a dash otherwise. */
/** The period billed, or for an invoice without one (Fixed Price), its lines, which are the
 * milestones' descriptions when they were generated. A long list is clipped to the column. */
export function BilledForCell({ invoice }: { invoice: InvoiceListItem }) {
  if (invoice.period_start && invoice.period_end) {
    return (
      <>{formatPeriod(parseDayKey(invoice.period_start), parseDayKey(invoice.period_end))}</>
    );
  }
  if (!invoice.lines_summary) return <>—</>;
  return <span className="block max-w-64 truncate">{invoice.lines_summary}</span>;
}

/**
 * A fixed due date as a date. A payment terms preset cannot be turned into a date before
 * the invoice is issued, so a draft shows the preset's name, muted, and says why.
 */
export function DueCell({ invoice }: { invoice: InvoiceListItem }) {
  const { t } = useTranslation(["invoices"]);
  if (invoice.due_date) return <>{formatDueDate(invoice.due_date)}</>;
  if (!invoice.payment_terms) return null;
  // Own provider: only the navigation bar mounts one.
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="text-muted-foreground" tabIndex={0}>
            {t(PAYMENT_TERMS_LABELS[invoice.payment_terms])}
          </span>
        </TooltipTrigger>
        <TooltipContent>{t("Calculated when the invoice is issued")}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/** The invoice date, with the full moment it was issued in a tooltip; empty on a draft. */
export function IssuedCell({ invoice }: { invoice: InvoiceListItem }) {
  if (!invoice.invoice_date) return null;
  const date = formatDueDate(invoice.invoice_date);
  if (!invoice.issued_at) return <>{date}</>;
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0}>{date}</span>
        </TooltipTrigger>
        <TooltipContent>{new Date(invoice.issued_at).toLocaleString()}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Issued and Due are optional: a date that matters once an invoice is issued, so they start
// hidden and the "Columns" button shows them. Every other column is fixed.
const DEFAULT_COLUMN_VISIBILITY: ColumnVisibilityState = { issued: false, due: false };

// Labels for the "Columns" menu, keyed by column id and kept apart from the columns' headers,
// which are only rendered while the column is visible.
const HIDEABLE_COLUMN_LABELS: Record<string, string> = {
  issued: "Issued",
  due: "Due",
};

export interface InvoicesTableViewProps {
  items: InvoiceListItem[];
  sorting: SortingState;
  onSortingChange: OnChangeFn<SortingState>;
  pageCount: number;
  columnVisibility: ColumnVisibilityState;
  onColumnVisibilityChange: OnChangeFn<ColumnVisibilityState>;
  onOpen: (invoice: InvoiceListItem) => void;
  onDuplicate: (invoice: InvoiceListItem) => void;
  onDownload: (invoice: InvoiceListItem) => void;
  onDelete: (invoice: InvoiceListItem) => void;
}

export function InvoicesTableView({
  items,
  sorting,
  onSortingChange,
  pageCount,
  columnVisibility,
  onColumnVisibilityChange,
  onOpen,
  onDuplicate,
  onDownload,
  onDelete,
}: InvoicesTableViewProps) {
  const { t } = useTranslation(["invoices", "common"]);

  const columns: ColumnDef<typeof features, InvoiceListItem>[] = [
    {
      id: "number",
      enableHiding: false,
      accessorKey: "number",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Number")} />,
      // A draft has no number yet: its cell stays empty, and the link that covers the row is
      // named for assistive technology instead.
      cell: ({ row }) =>
        row.original.number ? (
          <RowLink to={`/invoices/${row.original.id}`} className="font-mono">
            {row.original.number}
          </RowLink>
        ) : (
          <RowLink
            to={`/invoices/${row.original.id}`}
            aria-label={t("Edit invoice for {{project}}", {
              project: row.original.project_name,
            })}
          />
        ),
    },
    {
      id: "status",
      enableHiding: false,
      accessorKey: "status",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Status")} />,
      cell: ({ row }) => (
        <Badge variant={STATUS_BADGE_VARIANT[row.original.status]}>
          {t(INVOICE_STATUS_LABELS[row.original.status])}
        </Badge>
      ),
    },
    {
      id: "project",
      enableHiding: false,
      accessorKey: "project_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Project")} />,
    },
    {
      id: "client",
      enableHiding: false,
      accessorKey: "client_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Client")} />,
    },
    {
      id: "billed_for",
      enableHiding: false,
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title={t("Billed for")} />
      ),
      cell: ({ row }) => <BilledForCell invoice={row.original} />,
    },
    {
      id: "created_at",
      enableHiding: false,
      accessorKey: "created_at",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Created")} />,
      cell: ({ row }) => new Date(row.original.created_at).toLocaleDateString(),
    },
    {
      id: "total",
      enableHiding: false,
      accessorKey: "total",
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Total")} />,
      cell: ({ row }) => (
        <span className="tabular-nums">
          {formatMoney(row.original.total, row.original.currency_minor_unit)}{" "}
          {row.original.currency_code}
        </span>
      ),
    },
    {
      id: "issued",
      enableHiding: true,
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Issued")} />,
      cell: ({ row }) => <IssuedCell invoice={row.original} />,
    },
    {
      id: "due",
      enableHiding: true,
      header: ({ column }) => <DataTableColumnHeader column={column} title={t("Due")} />,
      cell: ({ row }) => <DueCell invoice={row.original} />,
    },
    {
      id: "actions",
      enableHiding: false,
      header: "",
      enableSorting: false,
      cell: ({ row }) => (
        // Above the link that covers the row, so the menu opens instead of the invoice.
        <div className="relative z-10 flex justify-end">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">{t("Actions", { ns: "common" })}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onOpen(row.original)}>
                {row.original.status === "draft"
                  ? t("Edit", { ns: "common" })
                  : t("View", { ns: "common" })}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDuplicate(row.original)}>
                {t("Duplicate", { ns: "common" })}
              </DropdownMenuItem>
              {canDownloadPdf(row.original) && (
                <DropdownMenuItem onClick={() => onDownload(row.original)}>
                  {t("Download PDF")}
                </DropdownMenuItem>
              )}
              {row.original.status === "draft" && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => onDelete(row.original)}
                  >
                    {t("Delete", { ns: "common" })}
                  </DropdownMenuItem>
                </>
              )}
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
    // Sorted and paginated by the server: see components/data-table/sorting.ts.
    manualPagination: true,
    manualSorting: true,
    pageCount,
    state: { columnVisibility, sorting },
    onSortingChange,
    onColumnVisibilityChange,
  });

  return (
    <DataTable
      table={table}
      columnCount={table.getVisibleLeafColumns().length}
      emptyMessage={t("No invoices yet")}
    />
  );
}

// Same pause as the Projects and Users searches: a request per keystroke is wasted work.
const SEARCH_DEBOUNCE_MS = 300;

export function InvoicesTable() {
  const navigate = useNavigate();
  const { t } = useTranslation(["invoices", "common"]);

  const [items, setItems] = useState<InvoiceListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState<string[]>([]);
  // Not remembered: the choice lasts until the page is left, like the Projects list.
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>(
    DEFAULT_COLUMN_VISIBILITY,
  );
  // Void invoices are kept as evidence but hidden unless asked for.
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus[]>(DEFAULT_STATUS_FILTER);
  const [projectOptions, setProjectOptions] = useState<ReportFilterOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<InvoiceListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  // A new sort or filter changes what page 1 is, so both reset the page in the same
  // render rather than fetching once with the old page.
  const handleSortingChange: OnChangeFn<SortingState> = (updater) => {
    setSorting(updater);
    setPage(1);
  };

  // The dropdown allows several; this filter takes one project, the last one picked.
  function handleStatusFilter(next: string[]) {
    setStatusFilter(next as InvoiceStatus[]);
    setPage(1);
  }

  function handleProjectFilter(next: string[]) {
    const added = next.filter((id) => !projectFilter.includes(id));
    setProjectFilter(added.length ? [added[added.length - 1]] : []);
    setPage(1);
  }

  // A search changes what page 1 is, so the page resets with it.
  useEffect(() => {
    const handle = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    listInvoiceProjects({ invoiced: true })
      .then((projects) => {
        if (!cancelled) setProjectOptions(projects.map((p) => ({ id: p.id, label: p.name })));
      })
      .catch(() => {
        // The list still works without its filter.
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  useEffect(() => {
    let cancelled = false;
    listInvoices({
      page,
      projectId: projectFilter[0],
      search: search || undefined,
      // Nothing ticked reads as the default rather than as "show nothing".
      statuses: statusFilter.length ? statusFilter : DEFAULT_STATUS_FILTER,
      ...toSortParams(sorting),
    })
      .then((response) => {
        if (cancelled) return;
        setError(null);
        setItems(response.items);
        setTotal(response.total);
        setPageSize(response.page_size);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : t("Failed to load invoices."));
      });
    return () => {
      cancelled = true;
    };
  }, [page, sorting, projectFilter, statusFilter, search, refreshToken, t]);

  async function handleDuplicate(invoice: InvoiceListItem) {
    try {
      const copy = await duplicateInvoice(invoice.id);
      toast.success(t("Invoice duplicated"));
      navigate(`/invoices/${copy.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to duplicate the invoice."));
    }
  }

  async function handleDownload(invoice: InvoiceListItem) {
    try {
      const { blob, filename } = await downloadInvoicePdf(invoice.id);
      downloadBlob(blob, filename ?? `${invoice.number ?? "invoice"}.pdf`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to download the PDF."));
    }
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deleteInvoice(deleteTarget.id);
      toast.success(t("Draft deleted"));
      setDeleteTarget(null);
      setRefreshToken((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete the draft."));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {/* First, like the other lists. On a phone the box takes the whole row and the filters
            wrap under it. */}
        <Input
          placeholder={t("Search invoices…")}
          aria-label={t("Search invoices…")}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="w-full sm:w-96"
        />
        <ReportFilterDropdown
          label={t("Status")}
          icon={ListFilter}
          options={INVOICE_STATUSES.map((status) => ({
            id: status,
            label: t(INVOICE_STATUS_LABELS[status]),
          }))}
          selected={statusFilter}
          onChange={handleStatusFilter}
          searchable={false}
        />
        <ReportFilterDropdown
          label={t("Project")}
          icon={FolderKanban}
          options={projectOptions}
          selected={projectFilter}
          onChange={handleProjectFilter}
        />
        <div className="ml-auto flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Columns3 className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("Columns", { ns: "common" })}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {Object.entries(HIDEABLE_COLUMN_LABELS).map(([id, label]) => (
                <DropdownMenuCheckboxItem
                  key={id}
                  checked={columnVisibility[id] !== false}
                  onCheckedChange={(checked) =>
                    setColumnVisibility((current) => ({ ...current, [id]: !!checked }))
                  }
                  onSelect={(e) => e.preventDefault()}
                >
                  {t(label)}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button onClick={() => navigate("/invoices/new")}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("New", { ns: "common" })}
          </Button>
        </div>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <InvoicesTableView
        items={items}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        pageCount={Math.max(1, Math.ceil(total / pageSize))}
        columnVisibility={columnVisibility}
        onColumnVisibilityChange={setColumnVisibility}
        onOpen={(invoice) => navigate(`/invoices/${invoice.id}`)}
        onDuplicate={(invoice) => void handleDuplicate(invoice)}
        onDownload={(invoice) => void handleDownload(invoice)}
        onDelete={setDeleteTarget}
      />

      <DataTablePagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        countLabel={t("invoiceCount", { count: total })}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("Delete the draft for {{project}}?", { project: deleteTarget?.project_name })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("The draft and its lines are removed for good.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>
              {t("Cancel", { ns: "common" })}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={isDeleting}
              onClick={() => void handleConfirmDelete()}
            >
              {isDeleting && <Spinner />}
              {isDeleting ? t("Deleting…", { ns: "common" }) : t("Delete", { ns: "common" })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
