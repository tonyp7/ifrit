import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import type { Role } from "@/types/user";

// Route-level guard mirroring the nav bar's visibility rules (see
// src/config/navigation.ts) so a role can't reach a screen by typing its URL
// directly, even though it's already hidden from their nav bar.
export function RequireRoles({ roles }: { roles: Role[] }) {
  const { user } = useAuth();

  const hasAccess = user !== null && roles.some((role) => user.roles.includes(role));

  if (!hasAccess) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
