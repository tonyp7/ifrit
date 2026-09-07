# Infrastructure, Deployment and CI/CD NFR

**Implemented**: `docker/Dockerfile`, `docker/nginx.conf`, `docker/entrypoint.sh`,
`docker/build.sh`, root `docker-compose.yml`, and root `.env.example` — this section is now
the description of what those files actually do, not a plan. See `docker/Dockerfile`'s own
header comment for the two points deliberately left unresolved (no auto-seeding of the
bootstrap admin, uvicorn running as root inside the container) rather than decided silently.

## Containerisation

- **Backend base image**: the backend build stage must run on Debian Trixie Slim
  (`python:3.12-slim-trixie` or `debian:trixie-slim` with Python installed via `uv`) — do not
  switch to Alpine or a different Debian release without updating this file.
- **Single multi-stage build**: the app is built as one multi-stage `Dockerfile` that produces
  a single combined container image for front-end and back-end — there is no separate `web`
  container:
  1. **Frontend build stage**: Node stage builds the Vite SPA (`pnpm build`) and produces the
     static `dist/` output.
  2. **Backend stage**: Debian Trixie Slim stage installs the FastAPI app (via `uv`).
  3. **Final stage**: nginx serves the static files copied from the frontend build stage, and
     reverse-proxies API requests (e.g. `/api/*`) to the FastAPI process (uvicorn) within the
     same container, via a single `nginx.conf`. Both nginx and uvicorn run in this one
     container (e.g. supervised by a lightweight process manager or entrypoint script).
- Docker files: `docker/` (or a per-service `Dockerfile` alongside each app) + root
  `docker-compose.yml`

## Deployment

- The `docker-compose` stack has two services:
  - **app**: the combined multi-stage image described above (nginx + static frontend + FastAPI)
  - **db**: PostgreSQL 18 — use the standard, unmodified `postgres:18` image; no custom
    Postgres image or Dockerfile for this service

```bash
# Build and run the full stack (app + db)
docker compose up --build

# Tear down
docker compose down
```

AI agents should never run these commands directly unless instructed.

### Local Development

`docker-compose.dev.yml` (repo root) is dev-only: it runs a standalone, unmodified
`postgres:18` container so the backend can be run natively (`uv run uvicorn ...`) against a
real database without building the production image. It is not used for deployment and has no
`app` service.

```bash
docker compose -f docker-compose.dev.yml up -d
```

## Configuration & Secrets

- Backend config via environment variables (`.env` for local dev, never committed)
- Secrets (JWT signing key, DB credentials) come from the environment / compose secrets,
  never hardcoded
- For the `docker-compose.yml` stack specifically: copy root `.env.example` to `.env` (same
  directory as `docker-compose.yml`) and fill in real values — distinct from
  `backend/.env.example`, which is for running the backend natively against
  `docker-compose.dev.yml`'s database instead.

## CI/CD

<!-- TODO: define CI/CD pipeline conventions. -->
