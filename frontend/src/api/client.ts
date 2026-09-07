import { notifySessionExpired } from "@/api/sessionEvents";

const BASE_URL = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Endpoints exempt from the 401 -> refresh-and-retry interceptor below (see
// specs/requirements/auth.md's design doc, point 3):
// - /auth/refresh's own 401 is the "give up" signal the interceptor produces —
//   routing it back through the same logic would recurse forever.
// - /auth/login's 401 (wrong credentials) is a normal, expected outcome of that
//   specific call, not a session-expiry signal (see auth.md's User Stories: never
//   reveal whether an email is registered) — LoginPage handles it inline.
// - /auth/logout has no reason to try to refresh-and-retry itself.
const AUTH_EXEMPT_PATHS = ["/auth/refresh", "/auth/login", "/auth/logout"];

// /auth/me is the one path that should still attempt a silent refresh (that's what
// makes "remain active across reloads" actually work) but must NOT notify
// sessionExpired if that refresh fails — AuthProvider's own mount-time catch
// already handles that outcome correctly (setUser(null), which ProtectedRoute
// already turns into a redirect), so notifying too would just be a redundant
// second redirect attempt (see auth.md design doc, point 5).
const SILENT_REFRESH_PATHS = ["/auth/me"];

// Shared across concurrent requests so a burst of simultaneous 401s (e.g. a screen
// that fires several fetches on mount) triggers exactly one refresh call, not one
// per request — see auth.md design doc, point 1.
let refreshPromise: Promise<boolean> | null = null;

function attemptRefresh(): Promise<boolean> {
  refreshPromise ??= request<unknown>("/auth/refresh", { method: "POST" })
    .then(() => true)
    .catch(() => false)
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

async function throwApiError(response: Response): Promise<never> {
  let message = `Request failed with status ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      // A plain error message (most endpoints).
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      // FastAPI/Pydantic 422 validation errors: a list of {msg, loc, type}.
      message = body.detail
        .map((entry) =>
          entry && typeof entry === "object" && "msg" in entry
            ? String((entry as { msg: unknown }).msg)
            : String(entry),
        )
        .join("; ");
    }
  } catch {
    // response had no JSON body; keep the generic message
  }
  throw new ApiError(response.status, message);
}

async function request<T>(path: string, init?: RequestInit, isRetry = false): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    // Central 401 handling (see specs/requirements/auth.md's design doc) — a 401
    // means "you are not logged in," never a normal page-specific error, so this
    // is handled once here instead of by each of the app's screens independently.
    if (response.status === 401 && !isRetry && !AUTH_EXEMPT_PATHS.includes(path)) {
      const refreshed = await attemptRefresh();
      if (refreshed) {
        // Transparent retry: the original caller never sees this 401 at all.
        return request<T>(path, init, true);
      }
      if (!SILENT_REFRESH_PATHS.includes(path)) {
        notifySessionExpired();
      }
    }
    await throwApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
