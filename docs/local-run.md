# Local Run

If you want to run Ifrit locally for development purposes or because you prefer the app not to be containered, it is also entirely possible; although not the recommended way.

This guide explains how to do so.

The backend (FastAPI) and the frontend (Vite) run as two separate processes on your machine, and
talk to a PostgreSQL database. In development the frontend dev server serves the web interface on
port 5173 and forwards `/api` requests to the backend on port 8000.

## Prerequisites

| Tool | Notes |
|---|---|
| [Git](https://git-scm.com) | To clone the repository. |
| [uv](https://docs.astral.sh/uv/) | Runs the backend. It installs the Python version the backend needs (3.14 or later) by itself. |
| [Node.js](https://nodejs.org) 26 and [pnpm](https://pnpm.io) | Builds and runs the frontend. |
| PostgreSQL 18 | Either an instance you already have or a throwaway container, see below. |
| `libmagic` | System library used to check the real type of uploaded files. On Debian and Ubuntu it is the `libmagic1` package, on macOS `brew install libmagic`. |
| Liberation Sans fonts | Only needed for PDF export. On Debian and Ubuntu it is the `fonts-liberation` package. Without it, a PDF export fails with an error naming the missing package. |
| Noto Sans CJK fonts | Optional, for Chinese, Japanese and Korean text in the PDF export. On Debian and Ubuntu it is the `fonts-noto-cjk` package. Without it the export still works, and those characters print as empty boxes. |
| LibreOffice (Writer) | Only needed to preview invoices as PDF. On Debian and Ubuntu it is the `libreoffice-writer` package, on macOS `brew install --cask libreoffice`. Without it, Preview answers that the PDF engine is not available, and the tests that render an invoice are skipped. |

## Get the code

```shell
git clone https://github.com/tonyp7/ifrit.git
cd ifrit
```

## 1. Database

The backend needs a PostgreSQL database it can create tables in, and, to run the tests, a role that
is allowed to create databases.

The quickest way is the disposable container defined in `docker-compose.dev.yml`. It runs the
standard `postgres:18` image with the user, password and database all set to `ifrit`, and publishes
it on `localhost:5432`:

```shell
docker compose -f docker-compose.dev.yml up -d
```

!!! note
    `docker-compose.dev.yml` is only a database. It is not the application stack and is not meant
    for deployment; for that, see [Self-hosting](self-hosting.md).

If you would rather use a PostgreSQL you already have, create an empty database and a role for
Ifrit, and put its connection string in `DATABASE_URL` in the next step.

## 2. Backend

All backend commands run from the `backend` folder.

### Configure

```shell
cd backend
cp .env.example .env
```

!!! warning
    `backend/.env` is **not** the same file as the `.env` at the root of the repository. The root
    one belongs to the Docker Compose stack. This one is read only by the backend when you run it
    directly on your machine.

The defaults match the database container above, so most values can stay. Check these:

| Setting | What to do |
|---|---|
| `DATABASE_URL` | Keep the default for the container, or point it at your own database. Keep the `postgresql+asyncpg://` prefix. |
| `STORAGE_ROOT` | Set it to any writable directory on your machine (the example value is a placeholder), for example `/home/you/ifrit-storage`. Uploaded files are stored there. |
| `CORS_ORIGINS` | Keep `["http://localhost:5173"]`, the address of the frontend dev server. |
| `COOKIE_SECURE` | Keep `false`: a local `http://` address cannot use secure cookies. |
| `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD` | The administrator you will sign in with. The password needs at least 12 characters. |

Every setting is described in [Configuration](configuration.md).

### Create the schema and the first administrator

```shell
uv run alembic upgrade head
uv run python -m scripts.seed_admin
```

The first command creates the tables. The second creates the administrator defined by
`SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD`; a fresh database has no user at all. The first run of
`uv run` also creates a virtual environment in `backend/.venv` and installs the dependencies.

### Start the backend

```shell
uv run uvicorn app.main:app --reload
```

The API now listens on <http://localhost:8000> and restarts when you change a file.

## 3. Frontend

In a second terminal, from the root of the repository:

```shell
cd frontend
pnpm install
pnpm approve-builds
pnpm dev
```

`pnpm approve-builds` lets pnpm run the install scripts of the few dependencies that need one; it
asks you to confirm them. You only need to run it after an install that reports skipped builds.

Open <http://localhost:5173> and sign in with the administrator from step 2.

## Everyday commands

| Where | Command | What it does |
|---|---|---|
| `backend` | `uv run pytest -q` | Runs the backend tests. They need the database to be reachable, and create and use a second database named after yours with a `_test` suffix. |
| `backend` | `uv run ruff check .` | Lints the backend. |
| `frontend` | `pnpm test` | Runs the frontend tests. |
| `frontend` | `pnpm lint` | Lints the frontend. |
| `frontend` | `pnpm build` | Builds the frontend for production into `frontend/dist`. |

## Changing the database schema

Ifrit uses Alembic to manage the schema. A released migration is never edited: every schema change
is a new numbered migration in `backend/alembic/versions/`.

```shell
uv run alembic revision --autogenerate -m "description"   # generate a migration, then review it
uv run alembic upgrade head                               # apply it
```

To start over on a **development** database, drop and recreate it and run
`uv run alembic upgrade head` again. This destroys all of its data, so never do it on a database
you care about.

## Stopping

Stop the backend and the frontend with `Ctrl+C`. To stop the database container and keep its data:

```shell
docker compose -f docker-compose.dev.yml down
```

Add `-v` to also delete the database volume.
