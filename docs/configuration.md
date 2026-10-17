# Configuration

Ifrit is configured with environment variables. This page explains every one of them: what it does,
what to set it to, and what happens when you change it.

## How configuration works

With Docker Compose, the variables come from a `.env` file placed next to `docker-compose.yml`.
Start from the provided template:

```shell
cp .env.example .env
```

Then edit `.env` before starting the stack. Two rules apply:

- **Every setting is required.** The application has no built-in defaults and refuses to start when
  one is missing. Docker Compose also refuses to start when a variable it needs is empty.
- **Changes need a restart.** Settings are read when the container starts. After editing `.env`,
  run `docker compose up -d` again so the container is recreated with the new values.

!!! note
    The `.env` next to `docker-compose.yml` is not the same file as `backend/.env`. The latter is
    only used when you run the backend directly on your machine, see [Local Run](local-run.md).

A few options are not environment variables at all: they live in the application and are changed
by an administrator, see [Settings you change in the application](#settings-you-change-in-the-application).

## All variables at a glance

| Variable | Group | Example | Purpose |
|---|---|---|---|
| [`POSTGRES_USER`](#database) | Database | `ifrit` | Database role created in the `db` container. |
| [`POSTGRES_PASSWORD`](#database) | Database | a long random value | Password of that role. |
| [`POSTGRES_DB`](#database) | Database | `ifrit` | Name of the database. |
| [`DATABASE_URL`](#database) | Database | `postgresql+asyncpg://…` | Connection string; built for you by Compose, set it yourself only for an external database. |
| [`JWT_SECRET_KEY`](#sessions-and-security) | Security | output of `openssl rand -hex 32` | Secret that signs sessions. |
| [`JWT_ALGORITHM`](#sessions-and-security) | Security | `HS256` | Signing algorithm. |
| [`ACCESS_TOKEN_EXPIRE_MINUTES`](#sessions-and-security) | Security | `15` | Lifetime of a session's short-lived token. |
| [`REFRESH_TOKEN_EXPIRE_MINUTES`](#sessions-and-security) | Security | `10080` | How long a session lasts without activity. |
| [`CORS_ORIGINS`](#sessions-and-security) | Security | `["https://ifrit.mydomain.com"]` | Origins the application is served from. |
| [`COOKIE_SECURE`](#sessions-and-security) | Security | `true` | Makes session cookies HTTPS-only. |
| [`SEED_ADMIN_EMAIL`](#bootstrap-administrator) | Bootstrap | `admin@your-company.example` | Sign-in of the first administrator. |
| [`SEED_ADMIN_PASSWORD`](#bootstrap-administrator) | Bootstrap | a long random value | Password of the first administrator. |
| [`STORAGE_ROOT`](#uploads) | Uploads | `/app/storage` | Where uploaded files are kept. |
| [`MAX_UPLOAD_BYTES`](#uploads) | Uploads | `10485760` | Largest accepted upload, in bytes. |
| [`PGADMIN_EMAIL`](#optional-pgadmin-4) | Optional | `dba@your-company.com` | pgAdmin sign-in; only in a stack that includes pgAdmin. |
| [`PGADMIN_PASSWORD`](#optional-pgadmin-4) | Optional | a long random value | pgAdmin password; only in a stack that includes pgAdmin. |

## Database

The Compose stack runs a PostgreSQL 18 container named `db` and builds the application's connection
string from the first three variables below.

| Variable | Example | What it does |
|---|---|---|
| `POSTGRES_USER` | `ifrit` | The database role created in the `db` container. |
| `POSTGRES_PASSWORD` | a long random value | The role's password. Choose a real secret: it is the only protection of the data, and the stack does not publish the database port by default. |
| `POSTGRES_DB` | `ifrit` | The name of the database. |
| `DATABASE_URL` | `postgresql+asyncpg://ifrit:secret@db:5432/ifrit` | The connection string the application uses. |

You normally do not set `DATABASE_URL`: `docker-compose.yml` assembles it as
`postgresql+asyncpg://POSTGRES_USER:POSTGRES_PASSWORD@db:5432/POSTGRES_DB`.

**Using a database you already run.** Remove the `db` service from your compose file and set
`DATABASE_URL` yourself:

```text
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
```

Keep the `postgresql+asyncpg://` prefix: the driver part is required. If the password contains
characters such as `@`, `:` or `/`, URL-encode them.

!!! warning
    Changing `POSTGRES_USER`, `POSTGRES_PASSWORD` or `POSTGRES_DB` after the database has been
    created does not change the existing database: PostgreSQL only reads them on first start, when
    its data volume is empty. Change a password with SQL, then update `.env` to match.

## Sessions and security

Ifrit signs users in with signed tokens held in `httpOnly` cookies. These variables control how
they are signed, how long they last, and where they may be used.

| Variable | Example | What it does |
|---|---|---|
| `JWT_SECRET_KEY` | output of `openssl rand -hex 32` | The secret that signs every session. |
| `JWT_ALGORITHM` | `HS256` | The signing algorithm. Only `HS256`, `HS384` and `HS512` are accepted; anything else fails at startup. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Lifetime of the short-lived token that authorizes requests. The application renews it silently while the session is alive. |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `10080` | How long a session survives. 10080 minutes is 7 days; after that the user signs in again. |
| `CORS_ORIGINS` | `["https://ifrit.mydomain.com"]` | The exact origin or origins the application is reached on. |
| `COOKIE_SECURE` | `true` | Whether session cookies carry the `Secure` flag. |

### `JWT_SECRET_KEY`

Generate it once and keep it private:

```shell
openssl rand -hex 32
```

That produces 64 characters, which is long enough for all three algorithms. Never reuse the value
from another system, never commit it, and treat `.env` as a secret file.

Changing the key signs every user out immediately, because existing sessions no longer verify.

### `CORS_ORIGINS`

A JSON array of the origins users type in the browser, with scheme and without a trailing slash:

```text
CORS_ORIGINS=["https://ifrit.mydomain.com"]
```

List more than one origin if the application is reachable under several names:
`["https://ifrit.mydomain.com","https://timesheets.mydomain.com"]`. It must match the address in the
browser exactly, including `https` and any port.

!!! note
    For a deployment on your own machine, `localhost` with plain `http` is fine, together with
    `COOKIE_SECURE=false` (see [below](#cookie_secure)):

    ```text
    CORS_ORIGINS=["http://localhost"]
    COOKIE_SECURE=false
    ```

    If you publish the container on another port, include it in the origin, for example
    `["http://localhost:8080"]`. Only use this for a trial that nobody else can reach: anything
    served to other users should use HTTPS, a real domain name and `COOKIE_SECURE=true`.

### `COOKIE_SECURE`

The container itself serves plain HTTP on port 80 and expects TLS to be terminated in front of it,
see [Reverse Proxy](reverse-proxy.md).

| Value | Use it when |
|---|---|
| `true` | Users reach Ifrit over HTTPS. This is the right value for any real deployment. |
| `false` | You are only trying Ifrit on a plain `http://` address such as `http://localhost`. Many browsers refuse to keep a `Secure` cookie on plain HTTP, in which case sign-in does not stick with `true`. |

Leaving it `false` behind a TLS-terminating proxy sends session cookies without the `Secure` flag.

### Sessions end when

A user's sessions end immediately when they sign out, when an administrator resets their password,
and when their account is deactivated.

## Bootstrap administrator

| Variable | Example | What it does |
|---|---|---|
| `SEED_ADMIN_EMAIL` | `admin@your-company.example` | The sign-in email of the first administrator. |
| `SEED_ADMIN_PASSWORD` | a long random value | Its password: at least 12 characters. |

A new instance has no users, and these two settings do nothing on their own. Create the
administrator once, after the stack is running:

```shell
docker compose exec app python -m scripts.seed_admin
```

The command creates that account, or reports that it already exists and does nothing. Changing
`SEED_ADMIN_PASSWORD` later has no effect on an account that already exists: an administrator sets
a new password for it in **Configuration → Users**.

The application still requires both variables to be present on every start, so keep them in `.env`.

## Uploads

Ifrit stores the files users upload: the organization logo and project supporting documents. Two
variables control where they go and how large they may be.

| Variable | Example | What it does |
|---|---|---|
| `STORAGE_ROOT` | `/app/storage` | The folder, inside the container, where uploaded files are written. |
| `MAX_UPLOAD_BYTES` | `10485760` | The largest accepted upload, in bytes. `10485760` is 10 MiB. |

### Where files are stored

`STORAGE_ROOT` is a path **inside the container**. The compose file mounts the named volume
`ifrit-storage` at that path, so uploads survive restarts and rebuilds of the container. The default,
`/app/storage`, is right for almost everyone; if you do change it, the volume mount follows the
same variable, so there is nothing else to edit.

- Files are never served as static files. Every download goes through the application, which
  checks that the signed-in user is allowed to see the file.
- Back up the `ifrit-storage` volume together with the database, see
  [Backups](self-hosting.md#backups).
- Uploads only accept an allowlist of file types, and a file is checked against both its extension
  and its actual content. The organization logo accepts JPEG, PNG and WebP images.

### Changing the size limit

`MAX_UPLOAD_BYTES` is the limit the application enforces: a larger upload is refused and nothing is
stored. The limit applies to every upload.

There is a second limit in front of it. The web server inside the container accepts request bodies
of up to **11 MB** on the API, deliberately a little above the default to leave room for the
upload's own overhead. That value is built into the image and is **not** an environment variable.

| You want | What to do |
|---|---|
| A **smaller** limit | Lower `MAX_UPLOAD_BYTES` and restart. |
| About **10 MiB** (the default) | Nothing. |
| A **larger** limit | Raise `MAX_UPLOAD_BYTES`, **and** raise `client_max_body_size` in `docker/nginx.conf` to slightly above it, **and** rebuild the image. Then raise the limit of any reverse proxy in front too. |

Nothing keeps the two limits in sync. If you raise only `MAX_UPLOAD_BYTES`, uploads between 11 MB and
the new limit are rejected by the web server before they reach the application.

A reverse proxy in front of Ifrit has its own body-size limit, which must be at least as large as
the one above, see [Reverse Proxy](reverse-proxy.md).

## Optional: pgAdmin 4

pgAdmin is a web interface for managing a PostgreSQL database. It is **not** part of the default
`docker-compose.yml`. This section only applies to a stack that includes it, such as the example in
`docker/examples/nginx-ifrit-database-pgadmin`, which runs Ifrit, PostgreSQL and pgAdmin behind a
host nginx.

The example comes with its own `.env.example` (copy it to `.env` next to its `docker-compose.yml`). It
holds every variable above plus these two:

| Variable | Required | Example | What it does |
|---|---|---|---|
| `PGADMIN_EMAIL` | yes | `dba@your-company.com` | The email of the first pgAdmin user, used to sign in. |
| `PGADMIN_PASSWORD` | yes | a long random value | The password of that user. |

Both are required: Compose refuses to start the stack while either is empty. They are passed to
pgAdmin under the names its image reads, `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD`.

!!! note
    pgAdmin validates the email address and can reject one on a reserved domain such as `.local`.
    Use an address that looks like a real one.

### What the example sets for you

The `pgadmin` service of the example also sets these variables of the `dpage/pgadmin4` image. You do
not need to put them in `.env`; they are listed here so you know what to keep in step with your
reverse proxy.

| Variable | Value in the example | What it does |
|---|---|---|
| `SCRIPT_NAME` | `/pgadmin4` | Makes pgAdmin serve under the sub-path `/pgadmin4`. This must match the `location /pgadmin4/` of your reverse proxy, which then forwards the path unchanged with no rewrite. |
| `PGADMIN_CONFIG_SESSION_COOKIE_SECURE` | `"True"` | Marks pgAdmin's session cookie HTTPS-only. Any `PGADMIN_CONFIG_<SETTING>` variable overrides the pgAdmin setting of that name, and its value is written as a Python literal. Remove this one only if you reach pgAdmin over plain HTTP. |

Other variables of the image exist, for example `PGADMIN_LISTEN_PORT` (default `80` inside its
container); see the pgAdmin container documentation for the full list.

### Setting it up

1. Add `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` to `.env`, then start the stack. The email and
   password are only read the first time pgAdmin starts with an empty data volume: changing them in
   `.env` afterwards does not change the account, use pgAdmin's own user settings instead.
2. Its data lives in the named volume `ifrit-pgadmin` (`/var/lib/pgadmin` in the container), so its
   saved servers and settings survive restarts. Back it up if you care about them.
3. The example publishes pgAdmin only on the loopback address (`127.0.0.1:8082`), so it is
   reachable through your reverse proxy and not directly. Keep it that way, and put it behind TLS and
   preferably restricted access: it is a door to your database.
4. Open `https://your-domain/pgadmin4/`, sign in with the email and password above, and register a
   server with host `db`, port `5432`, and the database, user and password of
   [Database](#database). The host is `db` because pgAdmin and the database share the Compose
   network.

## Settings you change in the application

Some options are not environment variables and are changed by an administrator in the application,
under **Configuration → General**: the organization logo, whether and how large that logo is placed
on exported PDF reports, and the standard workday length. **Configuration → Invoices** holds the
document name that invoices carry. See [Administration](guide/administration.md#general).

## Example values

The same variables for a quick local trial and for a real deployment:

| Variable | Local trial | Real deployment |
|---|---|---|
| `POSTGRES_PASSWORD` | any password | a long random secret |
| `JWT_SECRET_KEY` | the output of `openssl rand -hex 32` | the output of `openssl rand -hex 32`, kept secret |
| `CORS_ORIGINS` | `["http://localhost"]` | `["https://ifrit.mydomain.com"]` |
| `COOKIE_SECURE` | `false` | `true` |
| `SEED_ADMIN_EMAIL` | the email you will sign in with | the first administrator's email |
| `SEED_ADMIN_PASSWORD` | at least 12 characters | a long random secret |

!!! warning
    `COOKIE_SECURE=false` and an `http://` origin are for a quick local test only. A real instance
    is served over HTTPS with `COOKIE_SECURE=true`. See [Self-hosting](self-hosting.md).
