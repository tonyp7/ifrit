import { notifySessionExpired } from "@/api/sessionEvents";

const BASE_URL = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Endpoints exempt from the 401 -> refresh-and-retry interceptor below:
// - /auth/refresh's own 401 is the "give up" signal the interceptor produces,
//   routing it back through the same logic would recurse forever.
// - /auth/login's 401 (wrong credentials) is a normal, expected outcome of that
//   specific call, not a session-expiry signal (the backend deliberately returns
//   a generic error so a failed login never reveals whether an email is
//   registered), LoginPage handles it inline.
// - /auth/logout has no reason to try to refresh-and-retry itself.
const AUTH_EXEMPT_PATHS = ["/auth/refresh", "/auth/login", "/auth/logout"];

// /auth/me is the one path that should still attempt a silent refresh (that's what
// makes "remain active across reloads" actually work) but must NOT notify
// sessionExpired if that refresh fails: AuthProvider's own mount-time catch
// already handles that outcome correctly (setUser(null), which ProtectedRoute
// already turns into a redirect), so notifying too would just be a redundant
// second redirect attempt.
const SILENT_REFRESH_PATHS = ["/auth/me"];

// Shared across concurrent requests so a burst of simultaneous 401s (e.g. a screen
// that fires several fetches on mount) triggers exactly one refresh call, not one
// per request.
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

// Turns an error response's JSON body into one user-facing message.
function messageFromBody(status: number, body: unknown): string {
  let message = `Request failed with status ${status}`;
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") {
    // A plain error message (most endpoints).
    message = detail;
  } else if (Array.isArray(detail)) {
    // FastAPI/Pydantic 422 validation errors: a list of {msg, loc, type}.
    message = detail
      .map((entry) =>
        entry && typeof entry === "object" && "msg" in entry
          ? String((entry as { msg: unknown }).msg)
          : String(entry),
      )
      .join("; ");
  }
  return message;
}

async function throwApiError(response: Response): Promise<never> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // response had no JSON body; keep the generic message
  }
  throw new ApiError(response.status, messageFromBody(response.status, body));
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
    // Central 401 handling: a 401 means "you are not logged in," never a normal
    // page-specific error, so this is handled once here instead of by each of the
    // app's screens independently.
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

// filename is parsed from Content-Disposition here (built server-side from the real
// project and consultant names) rather than recomputed by the caller.
function parseFilename(disposition: string | null): string | null {
  if (!disposition) return null;
  const match = /filename="?([^";]+)"?/.exec(disposition);
  return match ? match[1] : null;
}

async function requestBlob(
  path: string,
  isRetry = false,
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401 && !isRetry && !AUTH_EXEMPT_PATHS.includes(path)) {
      const refreshed = await attemptRefresh();
      if (refreshed) {
        return requestBlob(path, true);
      }
      notifySessionExpired();
    }
    await throwApiError(response);
  }

  const blob = await response.blob();
  return { blob, filename: parseFilename(response.headers.get("Content-Disposition")) };
}

export interface UploadOptions {
  method?: "POST" | "PUT";
  /** Called with 0-100 as the request body is sent. */
  onProgress?: (percent: number) => void;
}

// fetch cannot report upload progress, so uploads go through XMLHttpRequest. They share
// the 401 -> refresh-and-retry handling above, so an upload doesn't fail just because
// the short-lived access token expired while the user was choosing a file. No
// Content-Type is set: the browser must add the multipart boundary itself.
function requestUpload<T>(
  path: string,
  body: FormData,
  { method = "PUT", onProgress }: UploadOptions,
  isRetry = false,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, `${BASE_URL}${path}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };
    // Status 0 marks a request that never got a response (offline, aborted, timed out).
    xhr.onerror = () => reject(new ApiError(0, "Network error"));
    xhr.onabort = () => reject(new ApiError(0, "Upload aborted"));
    xhr.ontimeout = () => reject(new ApiError(0, "Upload timed out"));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new ApiError(xhr.status, "Unexpected response from the server"));
        }
        return;
      }

      let parsed: unknown = null;
      try {
        parsed = JSON.parse(xhr.responseText);
      } catch {
        // response had no JSON body; keep the generic message
      }
      const failure = new ApiError(xhr.status, messageFromBody(xhr.status, parsed));

      if (xhr.status === 401 && !isRetry) {
        void attemptRefresh().then((refreshed) => {
          if (refreshed) {
            requestUpload<T>(path, body, { method, onProgress }, true).then(resolve, reject);
          } else {
            notifySessionExpired();
            reject(failure);
          }
        });
        return;
      }
      reject(failure);
    };

    xhr.send(body);
  });
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  // For endpoints that return a file rather than JSON (e.g. Reporting's export)
  // same auth/401-refresh handling as `get`, but reads the response as a Blob
  // and surfaces the server-built filename instead of parsing a JSON body.
  getBlob: (path: string) => requestBlob(path),
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
  // multipart file upload with progress (see requestUpload)
  upload: <T>(path: string, body: FormData, options: UploadOptions = {}) =>
    requestUpload<T>(path, body, options),
};
