To run it locally

# 1. Dev database
docker compose -f docker-compose.dev.yml up -d

# 2. Backend
cd backend
cp .env.example .env
uv run alembic upgrade head
uv run python -m scripts.seed_admin      # creates admin@ifrit.local / changeme123
uv run uvicorn app.main:app --reload     # http://localhost:8000

# 3. Frontend (separate terminal)
cd frontend
pnpm install
pnpm approve-builds
pnpm dev                                 # http://localhost:5173
Log in with admin@ifrit.local / changeme123 — it should land on the empty placeholder dashboard.

One thing worth flagging: scripts/seed_admin.py is dev-only and documented as such, but there's no real user-registration/admin-creation flow yet (per the open question in user.md) — that's the natural next piece once you're ready to move past login.

## Production-shaped stack (Docker)

See [specs/architecture/infra.md](specs/architecture/infra.md) for the full picture. Short version:

    cp .env.example .env   # fill in real secrets, never commit .env
    docker compose up --build
    docker compose exec app python -m scripts.seed_admin   # first run only

This builds one combined image (nginx + the built SPA + FastAPI/uvicorn — `docker/Dockerfile`)
alongside a stock `postgres:18` container. Unlike the native-dev flow above, nothing seeds a
default admin automatically — see `docker/Dockerfile`'s header comment for why.

**`COOKIE_SECURE` is on you to verify.** It defaults to `false` in `Settings`
(`backend/app/core/config.py`) with no startup check forcing it otherwise — the app will happily
boot and serve auth cookies without the `Secure` flag if this is left unset or wrong. The
production `.env.example` above already sets `COOKIE_SECURE=true` as its example value, but
nothing enforces that once you copy and edit it. Before any real deployment, confirm `.env` has
`COOKIE_SECURE=true` and that TLS is actually terminated in front of this container (see
`docker/nginx.conf`) — this is a manual check on the deployer, not something the app fails fast
on.


uv run alembic stamp base   # reset bookkeeping only, no DDL
uv run alembic upgrade head # recreates tables fresh
uv run python -m scripts.seed_admin