# Agent Instructions for Ifrit

This document provides coding guidelines and best practices for contributing to Ifrit.

## Project Overview

Ifrit is a full-stack web application:

- **Backend**: Python 3.12+, FastAPI, JWT-based session management — see [Backend Architecture](specs/architecture/backend.md)
- **Frontend**: Vite + React/TypeScript SPA, mobile-first, shadcn/ui components — see [Frontend Architecture](specs/architecture/frontend.md)
- **Database**: PostgreSQL, accessed via SQLAlchemy 2.0 (async) with Alembic migrations — see [Database Architecture](specs/architecture/database.md)
- **Deployment**: Single `docker-compose` stack — one multi-stage container serving both
  front-end and back-end via nginx, plus a standard PostgreSQL 18 container — see
  [Infrastructure](specs/architecture/infra.md)

This file is a living document — as the codebase takes shape, keep it in sync with the
actual tools, scripts, and conventions in use rather than letting it drift.

## Architecture Documentation

Layer-specific conventions (code style, patterns, testing, dev commands) live under
[specs/architecture/](specs/architecture/index.md):

- [backend.md](specs/architecture/backend.md) — API design, back-end services
- [frontend.md](specs/architecture/frontend.md) — component structure, state management, styling rules, internationalisation
- [database.md](specs/architecture/database.md) — schema conventions, migrations, indexing rules
- [infra.md](specs/architecture/infra.md) — containerisation, deployment, CI/CD

## Dependency Policy

Agents must not add a new library/dependency (backend or frontend) unless it is already listed
in [backend.md](specs/architecture/backend.md) or [frontend.md](specs/architecture/frontend.md).
If a task appears to need a dependency not listed there, stop and get explicit user consent
before adding it — then update the relevant architecture doc to reflect the addition.

**Never assume a dependency choice — verify it against the actual project setup.** Two library
names can look interchangeable (same purpose, similar name, both associated with the same tool)
while only one actually works with this project's specific versions. Before adding a dependency,
check it's compatible with what's already here (e.g. this project is Tailwind **v4**, not v3 —
`tailwindcss-animate` is the v3-era JS-plugin equivalent and doesn't match this project's
CSS-first v4 config; the correct dependency for the same purpose here is `tw-animate-css`, per
[frontend.md](specs/architecture/frontend.md)). Install it for real and confirm it works
(type-checks, builds, actually produces the expected output) rather than trusting a name because
it's "the modern one" or "what the docs currently recommend" in general — verify against *this*
codebase's actual toolchain versions, since those versions can and do change (this exact example
flipped once already when the project migrated v3 → v4).

**shadcn/ui primitives must be added via the real CLI** (`npx shadcn@latest add <component>`),
never hand-written from memory, even when the target environment makes that CLI awkward to run
(e.g. a sandboxed shell without direct `node`/`npm` on `PATH` — find a way to reach the real
toolchain, such as invoking the host directly, rather than approximating the output by hand).
Hand-typed primitives drift from the canonical output in ways that are easy to miss and hard to
catch later — see [frontend.md](specs/architecture/frontend.md#component-patterns) for concrete
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

See [backend.md](specs/architecture/backend.md#testing) and
[frontend.md](specs/architecture/frontend.md#testing) for framework-specific testing conventions.

### Live UI verification (Playwright)

There is no Playwright MCP tool registered for this project (`claude mcp list` returns none) —
don't conclude from that alone that live browser verification is unavailable. Playwright itself
*is* usable here: run it as a plain npm package via Bash/Node, not through a dedicated tool.
Chromium builds are cached under `~/.cache/ms-playwright`, but the exact build a freshly
`npm install`ed `playwright` expects can be newer than what's cached — if `browserType.launch`
complains a browser executable doesn't exist, run `npx playwright install chromium` (skip
`--with-deps`, which needs interactive `sudo` and fails silently in a non-interactive shell) to
fetch the matching one, then re-run.

For a real end-to-end check against the actual dev stack (not just `tsc`/`eslint`/`build`, which
verify correctness, not feature behavior):

- Confirm the dev servers are already running before starting your own (`ps aux | grep -E
  "uvicorn|vite"`) — this project's convention is to reuse the ones already up rather than
  spawning duplicates.
- Log in as the seeded dev user (`admin@ifrit.local` / `changeme123`, from `.env`'s
  `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD` — see `backend/scripts/seed_admin.py`), which holds
  every role (`administrator`, `project_admin`, `project_manager`) precisely so one account can
  exercise any screen.
- Prefer existing dev DB data over inventing new fixtures — query it directly first (e.g. `docker
  exec ifrit-db-1 psql -U ifrit -d ifrit -c "..."`) to find a scenario that already fits (a
  project, service lines, assignments, time entries) before creating anything.
- If a test does mutate data (an edit, a lock), revert it afterward and verify via a direct DB
  query that row counts/state match what they were before — same "never leave the dev DB worse
  off than found" rule that applies to any other destructive testing.
- Write the script to a throwaway `.js` file in the session's scratchpad directory (`require("playwright")`,
  `chromium.launch()`), `npm install playwright` there first if needed, and clean up
  `node_modules`/`package.json` afterward — don't leave scratch npm installs behind either.

## Project-Specific Conventions

### Directory Structure (target layout)

- Backend code: `backend/` — see [backend.md](specs/architecture/backend.md)
- Frontend code: `frontend/` — see [frontend.md](specs/architecture/frontend.md)
- Database migrations: `backend/alembic/` — see [database.md](specs/architecture/database.md)
- Docker/deployment files — see [infra.md](specs/architecture/infra.md)
- Documentation: `specs/`

### Code Style Conformance

Once the codebase exists, always conform new and refactored code to the established patterns:

- Follow existing patterns in similar files
- Match indentation and formatting of surrounding code
- snake_case for Python, camelCase for TypeScript, PascalCase for React components
- Maintain the same level of verbosity in comments and docstrings as nearby code
