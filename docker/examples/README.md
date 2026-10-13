# Docker Compose examples

Ready-to-adapt Docker Compose stacks for running Ifrit in production behind a reverse proxy that
terminates TLS. Each example is a folder holding everything it needs: `docker-compose.yml`,
`.env.example` and the matching host `nginx.conf`.

| Example | Containers | Reverse proxy | Use it when |
|---|---|---|---|
| [`nginx-ifrit-database`](nginx-ifrit-database/) | `app` (Ifrit) and `db` (PostgreSQL 18) | Host nginx forwarding everything to the app on `127.0.0.1:8081` | You want the simplest production setup: Ifrit and its database, nothing else. |
| [`nginx-ifrit-database-pgadmin`](nginx-ifrit-database-pgadmin/) | `app`, `db` and `pgadmin` (pgAdmin 4) | Host nginx forwarding `/pgadmin4/` to pgAdmin on `127.0.0.1:8082` and everything else to the app on `127.0.0.1:8081` | You also want a web interface to inspect and manage the database. |

Both examples are the same except for the pgAdmin sidecar: in the second one, the `pgadmin` service,
its `ifrit-pgadmin` volume, the two `PGADMIN_*` variables in `.env.example` and the `/pgadmin4/`
locations in `nginx.conf` are added.

## How to use an example

1. Copy the folder you picked to your server.
2. Copy `.env.example` to `.env` (next to `docker-compose.yml`) and replace every `changeme` value
   with a real secret. Every variable is described in the
   [Configuration](https://docs.ifrit.day/configuration/) page.
3. Replace `ifrit.mydomain.com` with your domain in `nginx.conf` and in `CORS_ORIGINS`, and install
   `nginx.conf` as a site of your host nginx.
4. Start the stack, then create the first administrator:

    ```shell
    docker compose up -d
    docker compose exec app python -m scripts.seed_admin
    ```

## Things to know

- **Get the certificate first.** The `443` server block loads the Let's Encrypt certificate at
  start-up, so nginx will not start until it exists. Obtain it once with the port 80 block
  (it serves the `/.well-known/acme-challenge/` path from `/var/www/certbot`), then enable the
  TLS block.
- **Nothing is published to the internet by Docker.** The containers only listen on `127.0.0.1`;
  all outside traffic goes through the host nginx.
- **Pin the version.** The examples use the `:latest` tags for simplicity. In production, pin
  `ghcr.io/tonyp7/ifrit` to a release such as `:1.1.1`, and do the same for pgAdmin.
- **One stack per host.** Both examples set the Compose project name to `ifrit`, so they, and the
  root `docker-compose.yml` when run from a folder named `ifrit`, share the same volumes. Run only
  one of them on a given machine, or change `name:` in the file.
- **Upload size.** `client_max_body_size 20m` in `nginx.conf` must stay above `MAX_UPLOAD_BYTES`.
  See [Uploads](https://docs.ifrit.day/configuration/#uploads).
