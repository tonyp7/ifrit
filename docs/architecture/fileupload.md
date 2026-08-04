# File Upload & Repository — Non-Functional Requirements

This document defines mandatory behavior, security controls, and UX requirements for the file upload subsystem. Treat every requirement below as binding unless explicitly told otherwise for a specific feature.

---

## 1. Storage Architecture

- Files are stored on **local disk** under a configurable root (e.g. `/app/storage`), never inside the web-served static directory. Path must come from settings/env (`STORAGE_ROOT`), not be hardcoded.
- **Never** use the client-supplied filename as the on-disk path. Generate a SHA-256 hash per file.
- **Shard storage directories** by the first 2–4 hex chars of the hash to avoid flat directories with huge file counts:
  ```
  storage/{hash[0:2]}/{hash[2:4]}/{uuid}{ext}
  ```
- Extension used on disk must be derived from the **detected** MIME type (see §3), never the client-supplied extension.
- Writes must be atomic: write to a `.tmp` file, then `rename()` into place. No partial files should ever be readable at the final path.
- Storage directory must be mounted `noexec` where the OS supports it. Set files to non-executable permissions (`chmod 640`) on write.
- Do not expose the storage folder via any static file mount (`StaticFiles`, nginx `alias`, etc.). All reads happen through an authenticated API route that streams from disk.
- Before opening any path built from a DB-provided key, resolve it and verify it stays inside `STORAGE_ROOT` (defense in depth against path traversal, even though filenames are system-generated).

## 2. Database Schema (Metadata)

All file metadata lives in Postgres; binary content never does.

```sql
files (
  id UUID PRIMARY KEY,
  owner_id UUID REFERENCES users(id) NOT NULL,
  bucket_key TEXT NOT NULL,           -- on-disk relative path
  original_filename TEXT NOT NULL,    -- sanitized before storage, display-only
  detected_content_type TEXT NOT NULL,-- from magic-byte sniffing, not client header
  size_bytes BIGINT NOT NULL,
  checksum_sha256 TEXT NOT NULL,      -- for dedup + integrity verification
  status TEXT NOT NULL,               -- pending | scanning | processing | ready | rejected | failed
  rejection_reason TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  deleted_at TIMESTAMPTZ              -- soft delete
);
```

- Add a `file_permissions` join table if files can be shared across multiple users/resources beyond single ownership.
- `checksum_sha256` should be indexed/unique-constrained to support dedup: if a matching hash already exists and is `ready`, reference the existing blob instead of writing a duplicate.

## 3. Upload Validation Pipeline (mandatory, in order)

Every uploaded file must pass through all applicable steps before being marked `ready`. Reject on first failure.

1. **Size limits, enforced at two layers minimum:**
   - Reverse proxy (`client_max_body_size` or equivalent) rejects oversized requests before reaching the app.
   - FastAPI enforces a max size **while streaming** (never buffer the full upload into memory before checking size).
2. **Extension whitelist** — reject any file whose extension is not on an explicit allowlist for the given upload context.
3. **Content-type sniffing (magic bytes)** — detect the real MIME type from file bytes (e.g. `python-magic`), never trust the client's `Content-Type` header or filename extension. Reject if the detected type is not in the allowlist, or if the detected type doesn't match the claimed extension.
4. **Image re-encoding** — for any file accepted as an image, decode and re-render it from scratch (e.g. via Pillow) before persisting. This strips polyglot payloads, embedded scripts, and EXIF metadata. Never persist the original image bytes as-received.
5. **Non-image files** (PDF, docs, etc.) that cannot be safely re-rendered rely on steps 3, 6, and 7 as primary defenses.
6. **Archive handling** (if archives are accepted at all):
   - Check uncompressed total size and entry count *before* extraction; reject if either exceeds configured limits (zip-bomb protection).
   - Reject any archive entry whose path contains `..` or is absolute (zip-slip protection).
7. **Malware/AV scan** — every file is scanned (e.g. ClamAV via `clamd`) before being marked `ready`. Scanning runs as an async background task, not inline with the upload request. Status flow: `scanning` → `ready` or `rejected` (with `rejection_reason` populated, e.g. `"malware_detected"`).
8. **Filename sanitization for display** — `original_filename` stored for UI display must have control characters stripped and be length-capped (e.g. 255 chars), even though it is never used as a disk path.

## 4. Access Control

- Every upload and download endpoint requires a valid JWT and resolves the current user via standard auth dependency.
- Every read/download must verify the requesting user owns the file or has an explicit permission grant (via `file_permissions`) — checked against the DB, not inferred from the file path.
- No file is ever served directly from disk via a public/static route. All downloads stream through an authenticated endpoint (`FileResponse` or streaming response) after the ownership check.
- Downloads set `Content-Disposition: attachment` (forced download) for any non-pre-sanitized content, plus `X-Content-Type-Options: nosniff` to prevent browser MIME-sniffing exploits.

## 5. Upload Flow & Backend Behavior

- The upload endpoint (`UploadFile`) streams the request body to disk in chunks — never loads the entire file into memory.
- The endpoint returns a response **immediately after the file is safely written to disk**, with `status: "scanning"`. It does **not** block on AV scanning or image re-encoding — those run as background tasks (FastAPI `BackgroundTasks`, or a queue like Celery/RQ for higher volume).
- Status lifecycle, persisted in `files.status` and surfaced to the client:

  | Status | Meaning |
  |---|---|
  | `pending` | Upload initiated, not yet fully received |
  | `scanning` | Bytes received, AV scan / validation in progress |
  | `processing` | Post-scan work (e.g. image re-encoding, thumbnailing) |
  | `ready` | Passed all checks, available for download |
  | `rejected` | Failed validation/scan — file is deleted from disk, reason recorded |
  | `failed` | Unexpected error during processing |

- Rejected files must be deleted from disk immediately; do not retain rejected content.

## 6. Real-Time Status Updates (Frontend Contract)

Upload progress and post-upload processing status are **two distinct mechanisms** and must not be conflated:

- **Upload progress (%)** is tracked client-side only, via `XMLHttpRequest` `upload.onprogress` (or equivalent). No backend involvement — the browser already knows bytes sent.
- **Post-upload status** (`scanning` → `processing` → `ready`/`rejected`) must be pushed to the frontend via **Server-Sent Events** (`/api/files/{file_id}/status-stream`), since this is one-directional server→client and SSE is simpler than WebSocket for this use case (built-in browser reconnection, plain HTTP). WebSocket or polling are acceptable fallbacks if SSE is not viable in a given environment.
- The SSE stream closes automatically once a terminal status (`ready`, `rejected`, `failed`) is reached.
- Because `EventSource` cannot send custom auth headers, pass a short-lived scoped token as a query parameter over HTTPS, or use a `fetch` + `ReadableStream` implementation if header-based auth is required.

## 7. Frontend Requirements (React + shadcn/ui)

- Upload logic and status-stream logic are encapsulated in a single reusable hook (e.g. `useFileUpload`) exposing `{ status, progress, fileId, error, upload, reset }`. Components must not implement raw `XMLHttpRequest`/`EventSource` logic inline.
- UI must reflect every state distinctly:
  - `uploading` → `Progress` bar driven by client-side percentage.
  - `scanning` / `processing` → spinner (`lucide-react` `Loader2`) with descriptive label.
  - `ready` → success indicator + toast (`sonner`).
  - `rejected` → `Alert variant="destructive"` with the rejection reason; error toast.
  - `error` (network/unexpected) → distinct from `rejected`, with retry affordance.
- `EventSource` (or WebSocket) connections must be closed in a cleanup function (`useEffect` return) to avoid leaking open connections when a component unmounts mid-scan.
- Multiple concurrent uploads must be tracked independently (one hook instance / state entry per file), not as shared global state.
- Never render an uploaded file as clickable/downloadable in the UI until its status is `ready`.

## 8. Operational Requirements

- Disk usage must be monitored with alerting thresholds — unlike object storage, local disk is finite and can fill silently.
- Deduplication via `checksum_sha256`: identical content should not be stored twice; increment a reference count / link the existing record instead.
- Soft-delete (`deleted_at`) rather than hard-delete for user-facing removal, to support recovery and audit; physical disk cleanup can run as a separate periodic job for records past a retention window.
- All rejections must be logged with reason (`rejection_reason`) for audit and abuse-pattern monitoring.
- ClamAV signature definitions (`freshclam`) must auto-update on a schedule; treat scanning as signature-based and not a substitute for the other layers (extension/MIME validation, re-encoding, sandboxing).

---

## Summary Threat Matrix

| Threat | Required Control |
|---|---|
| Extension spoofing (`.jpg` that's really a script) | Magic-byte MIME detection (§3.3) |
| Polyglot files (valid image + embedded payload) | Image re-encoding from scratch (§3.4) |
| Malware / virus | AV scan before `ready` status (§3.7) |
| Executable uploads run server-side | Non-exec permissions, `noexec` mount (§1) |
| Path traversal via filename | UUID-based naming, resolved-path validation (§1) |
| Zip bombs / archive abuse | Pre-extraction size & entry checks (§3.6) |
| Zip-slip path traversal | Reject `..`/absolute entries in archives (§3.6) |
| Stored XSS via displayed filename | Filename sanitization for display (§3.8) |
| Browser MIME-sniffing exploits | `nosniff` header, forced attachment download (§4) |
| Unauthorized file access | Per-request ownership check against DB, no static mounts (§4) |
| Oversized upload DoS | Size limits at proxy + streaming app layer (§3.1) |
