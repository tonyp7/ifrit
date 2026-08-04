import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { MoreHorizontal, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { deactivateUser, listUsers, resetPassword } from "@/api/users";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/hooks/useAuth";
import { ROLE_LABELS, type User } from "@/types/user";
import { ResetPasswordDialog } from "@/components/users/ResetPasswordDialog";

const SEARCH_DEBOUNCE_MS = 300;

export function UsersTable() {
  const navigate = useNavigate();
  const { t } = useTranslation(["user", "common"]);
  const { user: currentUser } = useAuth();

  const [items, setItems] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  // Same debounce pattern as CompaniesTable — see
  // docs/requirements/company.md#companies-list-screen.
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
    listUsers({ search: search || undefined, page })
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
        setTotal(response.total);
        setPageSize(response.page_size);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : t("Failed to load users."));
      });
    return () => {
      cancelled = true;
    };
  }, [search, page, refreshToken, t]);

  function handleDuplicate(user: User) {
    // Client-side only, unlike Company's server-side /duplicate — name_id is
    // globally unique, so there's no valid placeholder to persist immediately. See
    // docs/requirements/user.md#user-form-create--edit--duplicate.
    navigate("/configuration/users/new", {
      state: { duplicateFrom: { roles: user.roles, is_sso: user.is_sso } },
    });
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deactivateUser(deleteTarget.id);
      toast.success(t("{{name}} deleted.", { name: deleteTarget.full_name }));
      setDeleteTarget(null);
      setRefreshToken((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("Failed to delete user."));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleResetPassword(newPassword: string) {
    if (!resetTarget) return;
    await resetPassword(resetTarget.id, newPassword);
    toast.success(t("Password reset for {{name}}.", { name: resetTarget.full_name }));
    setResetTarget(null);
  }

  const columns: ColumnDef<User>[] = [
    {
      accessorKey: "full_name",
      header: t("Name", { ns: "common" }),
    },
    {
      accessorKey: "name_id",
      header: t("Login identity"),
    },
    {
      accessorKey: "roles",
      header: t("Roles"),
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {row.original.roles.map((role) => (
            <Badge key={role} variant="secondary">
              {t(ROLE_LABELS[role])}
            </Badge>
          ))}
        </div>
      ),
    },
    {
      accessorKey: "is_sso",
      header: t("Login method"),
      cell: ({ row }) => (row.original.is_sso ? t("SSO") : t("Local")),
    },
    {
      accessorKey: "is_active",
      header: t("Status"),
      cell: ({ row }) => (
        <Badge variant={row.original.is_active ? "default" : "secondary"}>
          {row.original.is_active ? t("Active", { ns: "common" }) : t("Inactive", { ns: "common" })}
        </Badge>
      ),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => {
        const isSelf = row.original.id === currentUser?.id;
        return (
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
                  onClick={() => navigate(`/configuration/users/${row.original.id}`)}
                >
                  {t("Edit", { ns: "common" })}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleDuplicate(row.original)}>
                  {t("Duplicate", { ns: "common" })}
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={row.original.is_sso}
                  onClick={() => setResetTarget(row.original)}
                >
                  {t("Reset Password")}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  disabled={isSelf}
                  className="text-destructive focus:text-destructive"
                  onClick={() => setDeleteTarget(row.original)}
                >
                  {t("Delete", { ns: "common" })}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualFiltering: true,
    manualPagination: true,
    pageCount: Math.max(1, Math.ceil(total / pageSize)),
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <Input
          placeholder={t("Search by name or login identity…")}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-sm"
        />
        <Button onClick={() => navigate("/configuration/users/new")}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("New", { ns: "common" })}
        </Button>
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
                  {t("No users found.")}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{t("userCount", { count: total })}</p>
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
              {t("Delete {{name}}?", { name: deleteTarget?.full_name })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t(
                "This deactivates the user (it can't be reactivated from the UI currently). They will no longer be able to log in.",
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

      <ResetPasswordDialog
        open={resetTarget !== null}
        onOpenChange={(open) => !open && setResetTarget(null)}
        userName={resetTarget?.full_name ?? ""}
        onConfirm={handleResetPassword}
      />
    </div>
  );
}
