# Configuration

Ifrit is configured through environment variables. With Docker Compose they come from the `.env`
file next to `docker-compose.yml`; start from the provided `.env.example`:

```shell
cp .env.example .env
```

Every setting below is required: the application has no built-in defaults and refuses to start
when one is missing. The compose file also refuses to start when a variable it needs is empty.

!!! note
    The `.env` next to `docker-compose.yml` is not the same file as `backend/.env.example`. The
    latter is only for people running the backend directly on their machine while developing.

## Database

The compose stack runs a PostgreSQL 18 container and builds the connection string for the
application from these three settings.

| Setting | Example | Description |
|---|---|---|
| `POSTGRES_USER` | `ifrit` | Database role created in the `db` container. |
| `POSTGRES_PASSWORD` | a long random value | Password for that role. Choose a real secret. |
| `POSTGRES_DB` | `ifrit` | Name of the database. |

The resulting `DATABASE_URL` is
`postgresql+asyncpg://USER:PASSWORD@db:5432/DATABASE`. To use a database of your own, set
`DATABASE_URL` yourself (see [Use your own PostgreSQL](self-hosting.md#use-your-own-postgresql)).

## Sessions and security

| Setting | Example | Description |
|---|---|---|
| `JWT_SECRET_KEY` | output of `openssl rand -hex 32` | Secret used to sign sessions. Keep it private and never reuse it elsewhere. Changing it signs everyone out. |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm. Only `HS256`, `HS384` and `HS512` are accepted. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | How long a session's access token is valid. The application renews it silently while the refresh token is valid. |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `10080` | How long a session survives without a renewal: 10080 minutes is 7 days. After that the user signs in again. |
| `CORS_ORIGINS` | `["https://ifrit.mydomain.com"]` | JSON array of the exact origins the application is served from, scheme included. Use `["http://localhost"]` only for a local trial. |
| `COOKIE_SECURE` | `true` | `true` makes the session cookies HTTPS-only. Set `true` wherever TLS is in place; `false` only works for a plain `http://` trial. |

Sessions are carried in `httpOnly` cookies. Signing out, an administrator resetting a user's
password, and deactivating a user all end that user's existing sessions immediately.

## Bootstrap administrator

| Setting | Example | Description |
|---|---|---|
| `SEED_ADMIN_EMAIL` | `admin@your-company.example` | Sign-in email of the first administrator. |
| `SEED_ADMIN_PASSWORD` | a long random value | Password for it: at least 12 characters. |

These two settings do nothing on their own. A new instance has no users until you run:

```shell
docker compose exec app python -m scripts.seed_admin
```

The command creates that administrator, or prints a message and does nothing when the account
already exists.

## Uploads

| Setting | Example | Description |
|---|---|---|
| `STORAGE_ROOT` | `/app/storage` | Where uploaded files are stored inside the container. The compose file mounts the named volume `ifrit-storage` here so uploads survive rebuilds. Keep the default unless you also change the volume mapping. |
| `MAX_UPLOAD_BYTES` | `10485760` | Largest accepted upload, in bytes (10485760 is 10 MiB). |

Uploaded files are never served as static files: each download goes through the application and
checks that the user is allowed to see it.

The web server inside the container accepts request bodies of up to 11 MB on the API, slightly
above the default limit to allow for the upload's own overhead. That value is built into the image
and is not a setting, so raising `MAX_UPLOAD_BYTES` above roughly 10 MiB requires changing the
image's nginx configuration (`docker/nginx.conf`, `client_max_body_size`) and rebuilding it. Any
proxy you put in front must allow the same size.

## Settings you change in the application

Some options live in the application rather than in `.env`, and are changed by an administrator
under **Configuration → General**: the organization logo and the PDF export logo options. See
[Administration](guide/administration.md#general).
