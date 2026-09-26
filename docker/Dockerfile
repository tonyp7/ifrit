# syntax=docker/dockerfile:1
#
# Single multi-stage build producing one combined image (nginx + static frontend +
# FastAPI/uvicorn). There is no separate "web" image; this is intentionally the
# only Dockerfile for the app.
#
# Build from the REPO ROOT so both backend/ and frontend/ are in context:
#   docker build -f docker/Dockerfile -t ifrit-app .
# (docker/build.sh wraps this.)
#
# Unresolved / deliberately deferred (see the PR or ping before changing either):
# - scripts/seed_admin.py is NOT run automatically by docker/entrypoint.sh. Every
#   other deployment gets a genuinely admin-less database until someone runs it
#   by hand (`docker compose exec app python -m scripts.seed_admin`) — see
#   .env.example. Auto-seeding a known bootstrap account on every fresh
#   deployment felt like the wrong default to pick silently.
# - uvicorn and the migration step both run as root inside this container
#   (nginx's master process needs root to bind :80 either way; its workers
#   already drop to www-data via docker/nginx.conf's `user` directive). Dropping
#   uvicorn to a non-root user too (gosu/su-exec, or a dedicated USER + setuid)
#   is a reasonable hardening follow-up, not done here to keep this first pass
#   simple.

# ---------------------------------------------------------------------------
# Stage 1: frontend build — Vite SPA -> static dist/
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend-build
WORKDIR /src

# Pin the exact pnpm version rather than trusting whatever corepack defaults to,
# for reproducible builds — bump alongside frontend/pnpm-lock.yaml's own pnpm
# version if that ever changes.
RUN corepack enable && corepack prepare pnpm@11.18.0 --activate

# Dependencies first, in their own layer, so an app-code-only change doesn't bust
# the (slow) install cache.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ---------------------------------------------------------------------------
# Stage 2: backend build — installs the FastAPI app via uv, on Debian Trixie Slim
# (a deliberate choice other parts of this Dockerfile depend on, e.g. Stage 3's
# Debian-specific apt-get flow — don't switch base OS/arch without checking those)
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS backend-build
WORKDIR /app

# Official, pinned uv distribution image — see https://docs.astral.sh/uv/guides/integration/docker/
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /usr/local/bin/

# Dependencies first, in their own layer (same rationale as the frontend stage
# above) — `--no-install-project` skips installing the app package itself until
# the actual source is present.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend/ ./
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 3: final — nginx (serves the static SPA, reverse-proxies /api/* to
# uvicorn) + the backend venv, both running in this one container. Supervised by
# a plain entrypoint script (docker/entrypoint.sh) rather than a separate process
# manager package.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS final

# DEBIAN_FRONTEND=noninteractive is scoped to this RUN only (not ENV), so it
# never leaks into the final image's runtime environment. Without it, apt-get
# still installs nginx fine, but debconf wastes time/noise cascading through
# Dialog -> Readline -> Teletype frontends (none usable in a build layer with
# no TTY) before landing on Noninteractive anyway.
# fonts-liberation: the Reporting screen's PDF export (fpdf2) renders in
# Liberation Sans — this slim base image has no fonts installed at all otherwise.
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The fully-synced venv + application source from stage 2.
COPY --from=backend-build /app /app
ENV PATH="/app/.venv/bin:${PATH}"

# The built SPA from stage 1.
COPY --from=frontend-build /src/dist /usr/share/nginx/html

COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

# /api/health is unauthenticated and already implemented (backend/app/main.py).
# No curl/wget in this image; a stdlib check avoids adding either just for this.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request as u; u.urlopen('http://127.0.0.1/api/health', timeout=3)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
