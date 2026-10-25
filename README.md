<p align="center">
  <img alt="Ifrit logo" src="docs/static/img/ifrit.svg" height="160" width="160">
</p>

<h1 align="center">Ifrit Timesheet Tracker</h1>

<p align="center">
  A modern, open-source timesheet tracking and reporting application you host yourself.
</p>

<p align="center">
  <a href="https://github.com/tonyp7/ifrit/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/tonyp7/ifrit/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/tonyp7/ifrit/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/tonyp7/ifrit"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/github/license/tonyp7/ifrit"></a>
  <a href="https://github.com/tonyp7/ifrit/pkgs/container/ifrit"><img alt="Container image" src="https://img.shields.io/badge/ghcr.io-tonyp7%2Fifrit-blue?logo=docker&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://docs.ifrit.day/">Documentation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="https://github.com/tonyp7/ifrit/issues">Report an issue</a>
</p>

---

Ifrit is built for agencies, consultancies and any company where timesheets are at the core of the
business: people log their hours against projects, managers review and lock them, and the result is
exported as a report.

## Features

- **Time tracking.** A responsive timesheet by week or by month, with autosave. It works the same
  on a desktop and on a phone.
- **Projects.** Projects with service lines (quantity, unit and unit price), consultants assigned to
  each line, and supporting documents attached to the project.
- **Management.** Managers review the hours of everyone on their projects, correct them, and lock a
  period once it is final.
- **Companies.** Vendors and clients are recorded once, with their identifiers and addresses, and
  reused across projects.
- **Reports.** Filter by consultant, project, service line or status, then export to PDF, Excel or
  CSV.
- **Invoicing.** Billing prepares invoices for time and fixed-price projects from the hours logged or
  from billing milestones, adds taxes, issues and voids them with their own numbering, and gets a PDF
  made from a template you can edit.
- **Roles.** Consultants, managers, billing and administrators each see only the screens they need.
- **Light and dark themes**, following your system by default.
- **Self-hosted.** One container image plus PostgreSQL, started with Docker Compose. Database
  migrations run automatically when the container starts.

## Quick start

You need [Docker](https://docs.docker.com/get-docker/) with the Compose plugin. This starts a
throwaway instance on your own machine, with no configuration:

```shell
curl -O https://raw.githubusercontent.com/tonyp7/ifrit/main/docker/examples/local-docker-compose/docker-compose.yml
docker compose up -d
docker compose exec app python -m scripts.seed_admin
```

Then open <http://localhost:8081> and sign in with:

| Email | Password |
|---|---|
| `admin@ifrit.local` | `ifrit-local-trial` |

This setup is for trying Ifrit only: it is reachable from your machine alone, serves plain HTTP and
uses public default secrets. To run Ifrit for real, behind HTTPS on your own domain, follow the
self-hosting guide below.

## Documentation

Full documentation is at **[docs.ifrit.day](https://docs.ifrit.day/)**.

| I want to... | Read |
|---|---|
| Run Ifrit for my company | [Self-hosting](https://docs.ifrit.day/self-hosting/) |
| Look up every setting | [Configuration](https://docs.ifrit.day/configuration/) |
| Put Ifrit behind a reverse proxy | [Reverse proxy](https://docs.ifrit.day/reverse-proxy/) |
| Run it without Docker, for development | [Local run](https://docs.ifrit.day/local-run/) |
| Learn how to use it | [User guide](https://docs.ifrit.day/guide/roles/) |

Ready-made Compose and nginx files for a production setup are in
[`docker/examples`](docker/examples/).

## Releases

Ifrit follows [semantic versioning](https://semver.org). Each release is a `vX.Y.Z` tag and
publishes a container image to the GitHub Container Registry:

```text
ghcr.io/tonyp7/ifrit:2.2.0     an exact release (recommended for production)
ghcr.io/tonyp7/ifrit:2.2       the latest patch of 2.2
ghcr.io/tonyp7/ifrit:latest    the current state of main (not for production)
```

Read the [changelog](CHANGELOG.md) before upgrading, and back up first. Upgrading is covered in the
[self-hosting guide](https://docs.ifrit.day/self-hosting/).

## Built with

- **Backend:** Python, [FastAPI](https://fastapi.tiangolo.com), SQLAlchemy and Alembic
- **Frontend:** React and TypeScript, built with [Vite](https://vite.dev), UI from
  [shadcn/ui](https://ui.shadcn.com) and Tailwind CSS
- **Database:** PostgreSQL
- **PDF invoices:** [LibreOffice](https://www.libreoffice.org) (headless) turns an editable template
  into the PDF
- **Deployment:** a single multi-stage Docker image, with nginx serving the web interface

## Contributing

Bug reports and ideas are welcome in the [issue tracker](https://github.com/tonyp7/ifrit/issues).

To work on the code, follow [Local run](https://docs.ifrit.day/local-run/) to get the backend and
the frontend running on your machine. Please open a pull request from a branch, and make sure the
tests and linters pass first:

```shell
cd backend  && uv run pytest -q && uv run ruff check .
cd frontend && pnpm test && pnpm lint
```

## License

Ifrit is released under the [Apache License 2.0](LICENSE). Third-party material that needs credit,
such as the app's icon, is listed with its author and license in [ACKNOWLEDGMENTS](ACKNOWLEDGMENTS).
