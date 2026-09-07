# Backend Architecture — FastAPI

API design and back-end service conventions. See also: [Database](database.md), [Infrastructure](infra.md).

## Core Dependencies

Authorized backend dependencies (per the Dependency Policy in [AGENTS.md](../../AGENTS.md)):

- `fastapi`, `uvicorn[standard]` — web framework / ASGI server
- `sqlalchemy[asyncio]`, `asyncpg`, `alembic` — data layer (see [Database](database.md))
- `pydantic-settings` — environment-based config loading
- `pyjwt` — JWT issuance/validation
- `argon2-cffi` — password hashing (Argon2id) — not `bcrypt`: bcrypt only uses the first 72
  *bytes* of input, which conflicts with the 12–255 character/full-Unicode password policy (see
  [user.md § Password Policy](../requirements/user.md#password-policy)); Argon2 has no such
  practical limit
- `python-saml` — SSO / SAML 2.0 (see [auth.md](../requirements/auth.md))

## Python Requirements

- **Compatibility**: Python 3.12+
- **Package manager**: `uv` — use `uv add`/`uv remove` for dependencies, `uv run` to execute
  scripts, and commit `uv.lock`. Do not hand-edit `pyproject.toml` dependency pins.
- **Language features**: prefer modern Python — comprehensive type hints, dataclasses/Pydantic
  models over bare dicts, f-strings, `match` statements where they clarify branching,
  async/await for all I/O.

## Code Quality Standards

- **Formatting & linting**: Ruff (config in `pyproject.toml`)
- **Type checking**: mypy (or pyright), run in strict-ish mode; all public functions get type hints
- **Testing**: pytest (`pytest-asyncio` for async routes/services)
- **Language**: American English for code, comments, and docs
- **Punctuation**: no em dashes in code/comments/docs — use commas, colons, or separate sentences

## Authentication & Session Standards

- **JWT**: short-lived access tokens + longer-lived refresh tokens. Access tokens carry only
  the claims needed for authorization (subject, roles/scopes, expiry) — never embed sensitive
  data (passwords, secrets, PII beyond a user id) in a JWT payload, since it is not encrypted.
- **Transport**: both access and refresh tokens are set as `httpOnly`, `Secure`,
  `SameSite=Lax` cookies (not `Authorization` headers). This is viable because the SPA and
  API are same-origin in production (single container, nginx reverse-proxying `/api` to
  FastAPI — see [Infrastructure](infra.md)), and it keeps tokens out of reach of XSS via
  `localStorage`/JS. Applied consistently across all endpoints.
- **Secrets**: signing keys come from environment variables / secrets, never hardcoded or
  committed. Rotate-able via config, not a code change.
- **Password storage**: hash with `argon2-cffi` (Argon2id), never store or log plaintext
  passwords. See [user.md § Password Policy](../requirements/user.md#password-policy) for the
  length/character-set rule this choice exists to support, and why `bcrypt` doesn't work here.
- **SSO (SAML 2.0)**: `python-saml` is the authorized dependency for Azure Entra ID / SAML 2.0
  login (see [auth.md](../requirements/auth.md) for the user story). On a valid SAML assertion,
  the backend issues the same JWT access/refresh token pair as local login — SSO does not
  introduce a separate session mechanism. IdP metadata/certificates are configured via
  environment variables / secrets, never hardcoded.

## Logging Standards

- **Logger pattern**: module-level logger

  ```python
  import logging

  logger = logging.getLogger(__name__)
  ```

- **Format guidelines**:
  - No periods at end of log messages
  - No sensitive data (JWTs, passwords, tokens) in logs
  - Use lazy logging: `logger.debug("Message with %s", variable)`
- **Log levels**:
  - `debug`: development and troubleshooting information
  - `info`: important runtime events (startup, shutdown, auth events)
  - `warning`: recoverable issues that should be addressed
  - `error`: errors that affect functionality but don't crash the app
  - `exception`: use in `except` blocks to include traceback

## Error Handling

- **Exception types**: choose the most specific exception available
- **Try/except best practices**:
  - Only wrap code that can throw
  - Keep try blocks minimal — process results after the try/except, not inside it
  - Avoid bare `except Exception` outside of background-task boundaries
- **API errors**: never leak internal exception messages/stack traces in HTTP responses;
  log the detail server-side, return a safe generic message client-side

## Async Programming

- **External I/O**: all DB queries, HTTP calls, and file I/O must be async
- **Best practices**:
  - Use `asyncio.sleep()`, never `time.sleep()`, in async code
  - Use `asyncio.gather()` instead of awaiting in a loop when calls are independent
  - No blocking calls inside async functions (blocking DB drivers, `requests`, etc.)

## File Organization

- **Core**: `backend/app/core/` — settings (`config.py`), DB engine/session (`db.py`)
- **API routes**: `backend/app/api/` — FastAPI routers, grouped by resource
- **Auth**: `backend/app/auth/` — JWT issuance/validation, dependencies, password hashing
- **Models**: `backend/app/models/` — SQLAlchemy ORM models
- **Schemas**: `backend/app/schemas/` — Pydantic request/response models
- **Services**: `backend/app/services/` — business logic, kept out of route handlers
- **Migrations**: `backend/alembic/` — see [Database](database.md) for migration conventions

## API Endpoint Pattern

```python
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserOut)
async def read_current_user(user: UserOut = Depends(get_current_user)):
    return user
```

## Anti-Patterns to Avoid

Avoid:

```python
# Blocking operations in async functions
data = requests.get(url)  # use an async HTTP client (httpx)
time.sleep(5)  # use asyncio.sleep()

# Sensitive data in JWT payloads or logs
token = create_jwt({"password": user.password})  # never
logger.info(f"issued token {token}")  # never log tokens

# Leaking internals in API responses
except Exception as e:
    return JSONResponse(content={"error": str(e)})  # leaks internals
```

Use instead:

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(url)

await asyncio.sleep(5)

token = create_jwt({"sub": str(user.id), "roles": user.roles})

except Exception:
    logger.exception("Unhandled error in request")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

## Testing

- **Framework**: pytest + pytest-asyncio
- **Location**: `backend/tests/`
- **Coverage**: cover auth flows (login, refresh, expiry, invalid token) and any endpoint with
  authorization logic, in addition to core business logic
- Mock external services; use a real (test) Postgres database or a transactional rollback
  fixture rather than mocking the DB layer for integration tests
- **Isolated test database**: integration tests run against `settings.test_database_url`
  (`ifrit_test` by default), never `settings.database_url` (the dev database) — the
  `db_session` fixture auto-creates it if missing and drops all tables after every test
  (in a `finally`, so cleanup runs even when a test fails). The FastAPI app's `get_db`
  dependency is overridden per test to use this session. Sharing the dev database between
  the app and the test suite has previously wiped real dev data via `drop_all` — don't
  reintroduce that by pointing tests at `DATABASE_URL`.

## Development Commands

Run from `backend/`.

```bash
# Install dependencies
uv sync

# Run the dev server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Lint / format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy app

# Migrations — see Database for conventions
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```
