# Agent Instructions for Ifrit

This document provides coding guidelines and best practices for contributing to Ifrit.

## Project Overview

Ifrit is a full-stack web application:

- **Backend**: Python 3.12+, FastAPI, JWT-based session management — see [Backend Architecture](docs/architecture/backend.md)
- **Frontend**: Vite + React/TypeScript SPA, mobile-first, shadcn/ui components — see [Frontend Architecture](docs/architecture/frontend.md)
- **Database**: PostgreSQL, accessed via SQLAlchemy 2.0 (async) with Alembic migrations — see [Database Architecture](docs/architecture/database.md)
- **Deployment**: Single `docker-compose` stack — one multi-stage container serving both
  front-end and back-end via nginx, plus a standard PostgreSQL 18 container — see
  [Infrastructure](docs/architecture/infra.md)

This file is a living document — as the codebase takes shape, keep it in sync with the
actual tools, scripts, and conventions in use rather than letting it drift.

## Architecture Documentation

Layer-specific conventions (code style, patterns, testing, dev commands) live under
[docs/architecture/](docs/architecture/index.md):

- [backend.md](docs/architecture/backend.md) — API design, back-end services
- [frontend.md](docs/architecture/frontend.md) — component structure, state management, styling rules, internationalisation
- [database.md](docs/architecture/database.md) — schema conventions, migrations, indexing rules
- [infra.md](docs/architecture/infra.md) — containerisation, deployment, CI/CD

## Dependency Policy

Agents must not add a new library/dependency (backend or frontend) unless it is already listed
in [backend.md](docs/architecture/backend.md) or [frontend.md](docs/architecture/frontend.md).
If a task appears to need a dependency not listed there, stop and get explicit user consent
before adding it — then update the relevant architecture doc to reflect the addition.

**Never assume a dependency choice — verify it against the actual project setup.** Two library
names can look interchangeable (same purpose, similar name, both associated with the same tool)
while only one actually works with this project's specific versions. Before adding a dependency,
check it's compatible with what's already here (e.g. this project is Tailwind **v3**, not v4 —
`tw-animate-css` is a v4-only package and silently produces no working CSS under v3; the correct
dependency for the same purpose here is `tailwindcss-animate`). Install it for real and confirm
it works (type-checks, builds, actually produces the expected output) rather than trusting a
name because it's "the modern one" or "what the docs currently recommend" in general — verify
against *this* codebase's actual toolchain versions.

**shadcn/ui primitives must be added via the real CLI** (`npx shadcn@latest add <component>`),
never hand-written from memory, even when the target environment makes that CLI awkward to run
(e.g. a sandboxed shell without direct `node`/`npm` on `PATH` — find a way to reach the real
toolchain, such as invoking the host directly, rather than approximating the output by hand).
Hand-typed primitives drift from the canonical output in ways that are easy to miss and hard to
catch later — see [frontend.md](docs/architecture/frontend.md#component-patterns) for concrete
examples of bugs this caused in this codebase.

## Code Review Guidelines

When reviewing code, do NOT comment on:

- Missing imports — static analysis tooling catches these
- Code formatting — Ruff (Python) and Prettier (TypeScript) handle formatting
- Minor style inconsistencies already enforced by linters

## Testing Best Practices

- Every bug fix ships with a regression test
- Test edge cases and error paths, not just the happy path
- Prefer fixtures/factories over duplicated setup code

See [backend.md](docs/architecture/backend.md#testing) and
[frontend.md](docs/architecture/frontend.md#testing) for framework-specific testing conventions.

## Project-Specific Conventions

### Directory Structure (target layout)

- Backend code: `backend/` — see [backend.md](docs/architecture/backend.md)
- Frontend code: `frontend/` — see [frontend.md](docs/architecture/frontend.md)
- Database migrations: `backend/alembic/` — see [database.md](docs/architecture/database.md)
- Docker/deployment files — see [infra.md](docs/architecture/infra.md)
- Documentation: `docs/`

### Code Style Conformance

Once the codebase exists, always conform new and refactored code to the established patterns:

- Follow existing patterns in similar files
- Match indentation and formatting of surrounding code
- snake_case for Python, camelCase for TypeScript, PascalCase for React components
- Maintain the same level of verbosity in comments and docstrings as nearby code
