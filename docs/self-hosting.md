# Self-hosting

Docker Compose is the recommended way to run Ifrit. The repository's `docker-compose.yml` defines two
services:

- **app**: one container with nginx serving the web interface and reverse-proxying the API to the
  application server.
- **db**: a standard, unmodified PostgreSQL 18 container with a named volume (`ifrit-db`).

Uploaded files (the organization logo and project documents) live in a second named volume,
`ifrit-storage`, mounted at `STORAGE_ROOT` inside the app container.

If you have not run Ifrit yet, start with [Getting started](getting-started.md).

## Run it behind HTTPS

The application container serves plain HTTP on port 80. For a real deployment, put a reverse proxy
or load balancer that terminates TLS in front of it (nginx, Caddy, Traefik, a cloud load balancer),
and set:

```text
CORS_ORIGINS=["https://ifrit.mydomain.com"]
COOKIE_SECURE=true
```

- `CORS_ORIGINS` must list the exact origin users type in the browser, scheme included.
- `COOKIE_SECURE=true` makes the session cookies HTTPS-only. Leaving it `false` behind a TLS proxy
  would send session cookies without the `Secure` flag.

Your proxy must allow request bodies of at least 11 MB through, or uploads fail before they reach
the application (see [Uploads](configuration.md#uploads)).

## Use your own PostgreSQL

Inside the default stack the application reaches the database at host `db`. To use a database you
run yourself, remove the `db` service from your compose file and point `DATABASE_URL` at it:

```text
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
```

The `asyncpg` driver part of the URL is required. The compose file builds this URL from
`POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`; a custom `DATABASE_URL` replaces it.

## Releases and image tags

Ifrit follows [semantic versioning](https://semver.org). Each release is a `vX.Y.Z` tag on GitHub
and publishes a container image to the GitHub Container Registry:

| Image | What it is |
|---|---|
| `ghcr.io/tonyp7/ifrit:X.Y.Z` | An exact release. Recommended for production. |
| `ghcr.io/tonyp7/ifrit:X.Y` | The latest patch release of that minor version. |
| `ghcr.io/tonyp7/ifrit:X` | The latest release of that major version. |
| `ghcr.io/tonyp7/ifrit:latest` | The current state of `main`, which can be ahead of the last release. Not recommended for production. |

The provided `docker-compose.yml` builds the image from your checkout, so to run a release, check
out its tag:

```shell
git fetch --tags
git checkout vX.Y.Z
docker compose up -d --build
```

If you run your own compose file, use `image: ghcr.io/tonyp7/ifrit:X.Y.Z` in place of the `build:`
section of the `app` service, with the same environment variables and the same storage volume.

## Backups

Back up both of these together:

1. **The database**:

    ```shell
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > ifrit-backup.sql
    ```

2. **The uploaded files**: the `ifrit-storage` volume (for example with
   `docker run --rm -v ifrit-storage:/data -v "$PWD":/backup busybox tar czf /backup/ifrit-storage.tgz -C /data .`;
   note that Compose prefixes volume names with the project name, check `docker volume ls`).

To restore, recreate the stack, load the SQL dump into the database and put the files back into the
storage volume.

## Upgrading

1. Read the [changelog](https://github.com/tonyp7/ifrit/blob/main/CHANGELOG.md) for the release you
   are moving to.
2. **Take a backup** (above).
3. Check out the new tag (or change the image tag) and run `docker compose up -d --build`.

Database migrations are applied automatically every time the container starts, so there is no
separate migration step. Migrations only go forward: to return to an earlier release, restore your
backup.

## Security notes

- Generate a strong `JWT_SECRET_KEY` and keep `.env` out of version control and out of backups you
  share. Changing the key signs everyone out.
- Change `SEED_ADMIN_PASSWORD` after the first sign-in, or remove it from `.env` once the bootstrap
  administrator exists (the application still requires the setting to be present, so replace it
  with a long random value rather than deleting the line).
- Accounts are created by an administrator only. There is no self-registration and no
  self-service password reset: an administrator sets a new password for a user who forgot theirs.
