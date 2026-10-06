<p align="center">
  <img align="center" alt="logo" src="docs/static/img/ifrit.svg" height="256" width="256">
</p>

# Ifrit Timesheet Tracker

Ifrit Timesheet Tracker is a modern open-source timesheet tracking and reporting application that can be used by agencies, consultancies and other companies using timesheets as core to their business.

## Features

 - Time tracking: Fill in timesheets with a fully responsive modern UI interface
 - Projects: Create projects with service lines, assign people
 - Management: Assign project managers to specific projects
 - Companies: Create both vendor and client companies, and assign them to projects
 - Reports: Generate timesheets of individual contributors, entire projects or custom scopes
 - User Management: fine-grained user roles and permissions

## Self-Hosting Ifrit with Docker Compose

Docker Compose is simplest and recommended way to self-host your own instance of Ifrit.

### Steps to Running Ifrit

#### 1. Clone Repository

```shell
git clone https://github.com/tonyp7/ifrit.git
cd ifrit
```

#### 2. Create an .env file

Use the default .env file provided.

```shell
cp .env.example .env
```

#### 3. Security Considerations

##### JTW Secret
Update the `JWT_SECRET_KEY` by a proper value generated using openssl, or any other tool capable of generating a 32 bytes long random hex string.

```shell
openssl rand -hex 32
```

##### CORS and Secure Cookie
In .env, to run a local, HTTP only instance, you can set CORS to localhost and secure cookies to false:

```text
CORS_ORIGINS=["http://localhost"]
COOKIE_SECURE=false
```

**Warning:** A production server should have secure cookies enabled and be TLS terminated in front of the container. This should only be used for quick testing.

To run a proper instance on a server, edit your domain name and use HTTPS:

```text
CORS_ORIGINS=["https://ifrit.mydomain.com"]
COOKIE_SECURE=true
```

#### 4. Check if you need the containerized db

A simple `docker-compose.yml` is provided, that includes both the application and a containerized PostgreSQL.

Inside the default stack, the database runs on `db` and as such the connection string is by default `postgresql+asyncpg://${POSTGRES_USER:?}:${POSTGRES_PASSWORD:?}@db:5432/${POSTGRES_DB:?}`.

If you have your own PostgreSQL or if you want to separate it from the app stack, feel free to decouple them and update `DATABASE_URL` accordingly.

#### 5. Launch the instance

```shell
docker compose up -d --build
```

#### 6. Administrator bootstrap

A fresh instance of ifrit has no user. The first user (administrator role) can be created with `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` as login by running:

```shell
docker compose exec app python -m scripts.seed_admin
```

## Releases and Upgrading

Ifrit follows [semantic versioning](https://semver.org). Each release is a `vX.Y.Z` tag on GitHub, and publishes a container image to the GitHub Container Registry:

| Image | What it is |
|---|---|
| `ghcr.io/tonyp7/ifrit:1.0.0` | Exact. Recommended for production. |
| `ghcr.io/tonyp7/ifrit:1.0` | The latest patch release of 1.0. |
| `ghcr.io/tonyp7/ifrit:1` | The latest 1.x release. |
| `ghcr.io/tonyp7/ifrit:latest` | The current state of `main`, which can be ahead of the last release. Not recommended for production. |

The provided `docker-compose.yml` builds the image from your checkout, so to run a specific release, check out its tag:

```shell
git fetch --tags
git checkout v1.0.0
docker compose up -d --build
```

If you run your own compose file instead, use `image: ghcr.io/tonyp7/ifrit:1.0.0` in place of the `build:` section of the `app` service, with the same environment variables and storage volume as `docker-compose.yml`.

### Upgrading

1. Read the [changelog](CHANGELOG.md) for the release you are moving to.
2. **Back up first.** Dump the database, and copy the `ifrit-storage` volume, which holds the uploaded files:

   ```shell
   docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > ifrit-backup.sql
   ```

3. Check out the new tag (or change the image tag) and run `docker compose up -d --build`.

Database migrations are applied automatically each time the container starts, so there is no separate migration step. Migrations only go forward: to return to an earlier release, restore your backup.

## Running the app locally

If you wish to contribute to Ifrit's codebase or you do not want to use Docker, you can also run Ifrit locally. In this case, the simplest way is to launch the FastAPI backend with uv and launch the Vite frontend with pnpm.

### 1. Database

This assumes you already have a database running on host. Alternatively you can spin a standard postgres container.

### 2. Launch the backend

```shell
cd backend
cp .env.example .env
uv run alembic upgrade head
uv run python -m scripts.seed_admin      # creates SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD user
uv run uvicorn app.main:app --reload     # http://localhost:8000
```

Note that the .env file in `/backend` is not the same as .env as the root folder. The .env on the `/backend` is used for running locally the backend directly on host.

### 3. Launch frontend

In a separate terminal:

```shell
cd frontend
pnpm install
pnpm approve-builds
pnpm dev                                 # http://localhost:5173
```

### Maintenance

Ifrit uses Alembic to manage database migrations. A released migration is never edited: every schema change is a new numbered migration in `backend/alembic/versions/`.

```shell
uv run alembic revision --autogenerate -m "description"   # generate a migration, then review it
uv run alembic upgrade head                               # apply it
```

To start over on a **development** database, drop and recreate the database, then run `uv run alembic upgrade head` again. This destroys all of its data, so never do it on a database you care about.

## License and Acknowledgments

Ifrit is released under the [Apache License 2.0](LICENSE). Third-party material that needs credit,
such as the app's icon, is listed with its author and license in [ACKNOWLEDGMENTS](ACKNOWLEDGMENTS).
