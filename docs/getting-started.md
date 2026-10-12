# Getting started

This page gets a throwaway instance running on your own machine with Docker Compose in a few
minutes. For a real deployment, continue with [Self-hosting](self-hosting.md) afterwards.

## Requirements

- Docker with the Compose plugin
- Git
- `openssl` (or any tool that can generate a random hex string)

## 1. Get the code

```shell
git clone https://github.com/tonyp7/ifrit.git
cd ifrit
```

## 2. Create the `.env` file

```shell
cp .env.example .env
```

Open `.env` and set at least these values. [Configuration](configuration.md) describes every setting.

| Setting | For a local trial |
|---|---|
| `POSTGRES_PASSWORD` | any password; the database is only reachable from the stack |
| `JWT_SECRET_KEY` | the output of `openssl rand -hex 32` |
| `CORS_ORIGINS` | `["http://localhost"]` |
| `COOKIE_SECURE` | `false` (a plain `http://` instance cannot use secure cookies) |
| `SEED_ADMIN_EMAIL` | the email you will sign in with |
| `SEED_ADMIN_PASSWORD` | a password of at least 12 characters |

!!! warning
    `COOKIE_SECURE=false` and an `http://` origin are for a quick local test only. A real instance
    is served over HTTPS with `COOKIE_SECURE=true`. See [Self-hosting](self-hosting.md).

## 3. Start the stack

```shell
docker compose up -d --build
```

This builds the application image and starts it together with a PostgreSQL 18 database. Database
migrations run automatically each time the container starts.

## 4. Create the first administrator

A fresh instance has no user. Create the administrator defined by `SEED_ADMIN_EMAIL` and
`SEED_ADMIN_PASSWORD`:

```shell
docker compose exec app python -m scripts.seed_admin
```

## 5. Sign in

Open <http://localhost/> and sign in with the email and password from your `.env`. You land on your
own timesheet.

From here, an administrator typically:

1. creates the [companies](guide/administration.md#companies) (your own as vendor, and your clients),
2. creates the [users](guide/administration.md#users) and gives them roles,
3. lets a manager set up [projects](guide/projects.md).

## Stopping and removing

```shell
docker compose down        # stop, keep the data
docker compose down -v     # stop and DELETE the database and the uploaded files
```
