# Self-hosting

Docker Compose is the recommended way to run Ifrit. The repository's `docker-compose.yml` defines two
services:

- **app**: one container with nginx serving the web interface and reverse-proxying the API to the
  application server.
- **db**: a standard, unmodified PostgreSQL 18 container with a named volume (`ifrit-db`).

Uploaded files (the organization logo and project documents) live in a second named volume,
`ifrit-storage`, mounted at `STORAGE_ROOT` inside the app container.


## Get Prepared

There are two components outside of Ifrit that you may need:

**A database:** Ifrit's database is PostgreSQL. You may already have a database, containerised or not,
available for Ifrit. If this is the case, you will need to modify the connection string for the
database connectivity and databae environment variables accordingly.

**A reverse Proxy:** when using Ifrit for production, the containers should sit behind a reverse proxy (e.g. nginx, Traefik). This reverse proxy should carry TLS termination for the services. A few examples are given for ease of use.

Use a pre-built docker compose file available:

| Example | Description
|---|---|
| nginx-ifrit-database | A simple container with an attached containerised PgSQL
| nginx-ifrit-database-pagadmin | As above, but with an additional sidecar containing PgAdmin to manage the PostgreSQL database 


## Environment Variables

The compose file is accompanied by a `.env.example` file. Copy it to an actual environment file, before editing it, e.g.:

```shell
cp .env.example .env
```

See: [Configuration](configuration.md).

!!! warning
    These environment variables are critical to the app, and should be modified before starting.

## Start the app

Once the environment variables are set up you can simply run:

```shell
docker compose up -d
```

## Bootstrap Admin

A fresh instance of ifrit has no user. The first user (administrator role) can be created with `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` as login by running:

```shell
docker compose exec app python -m scripts.seed_admin
```


## Releases and image tags

Ifrit follows [semantic versioning](https://semver.org). Each release is a `vX.Y.Z` tag on GitHub
and publishes a container image to the GitHub Container Registry:

| Image | What it is |
|---|---|
| `ghcr.io/tonyp7/ifrit:X.Y.Z` | An exact release. Recommended for production. |
| `ghcr.io/tonyp7/ifrit:X.Y` | The latest patch release of that minor version. |
| `ghcr.io/tonyp7/ifrit:X` | The latest release of that major version. |
| `ghcr.io/tonyp7/ifrit:latest` | The current state of `main`, which can be ahead of the last release. Not recommended for production. |

!!! note
    The examples of compose files in the docker/examples subfolder use :latest tag for simplicity. In production, it is strongly advise to pin the stack to an actual version number.

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

### Upgrading from 1.x to 2.0

2.0 changes the database in ways that cannot be undone, so the backup above is not optional:

- **Roles.** The *project admin* and *project manager* roles become one **manager** role, and every
  user who held either becomes a manager. See
  [Upgrading from separate project roles](guide/roles.md#upgrading-from-separate-project-roles).
- **Invoices.** The invoicing tables are added. Once an invoice has been issued the database cannot be
  taken back to 1.x, even by the application: restore a backup instead.
- **A bigger image.** The image now contains LibreOffice, which makes the invoice PDFs, so it is about
  1.07 GB instead of about 497 MB. Leave room for it when you pull the image, and allow roughly
  250 MB of memory for each PDF being made (at most two at the same time) on top of what the
  application already uses. If you build your own image, it must include LibreOffice, otherwise
  issuing an invoice is refused with a "PDF engine is not available" error.
- **Time zone.** Set [`TZ`](configuration.md#time-zone) to your organization's time zone before you
  issue invoices: it decides the date on an invoice and the year, month and day in its number.

## Security notes

- Generate a strong `JWT_SECRET_KEY` and keep `.env` out of version control and out of backups you
  share. Changing the key signs everyone out.
- Change `SEED_ADMIN_PASSWORD` after the first sign-in, or remove it from `.env` once the bootstrap
  administrator exists (the application still requires the setting to be present, so replace it
  with a long random value rather than deleting the line).
- Accounts are created by an administrator only. There is no self-registration and no
  self-service password reset: an administrator sets a new password for a user who forgot theirs.
