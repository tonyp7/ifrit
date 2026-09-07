# Static Application Security Test (SAST) Report — Ifrit

**Scope:** Full source tree (`backend/`, `frontend/`, root config/infra files).
**Date:** 2026-08-05
**Method:** Manual static review (entry points → auth → data access → frontend), guided by
OWASP Top 10 (2021) and CWE Top 25. No code was modified as part of this pass.

## Stack identified

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Alembic migrations,
  PyJWT, `argon2-cffi` for password hashing, Pydantic/`pydantic-settings` for config and request
  validation.
- **Frontend**: React 18 + TypeScript, Vite, React Router, react-hook-form + Zod, i18next,
  Radix UI / Tailwind (shadcn-style components).
- **Data store**: PostgreSQL 18.
- **AuthN/Z**: Cookie-carried JWT access/refresh token pair (httpOnly), role-based dependency
  guards (`administrator` / `manager` / `consultant`) enforced server-side per router/endpoint.

Overall the backend consistently uses SQLAlchemy's expression API with bound parameters — no
raw string-interpolated SQL was found in application code. Object-scoping on nested resources
(e.g. addresses/identifiers under a company, service lines under a project, time entries under
the current user) is consistently enforced with compound `WHERE` clauses, so IDOR was not found
to be a broadly exploitable pattern here.

## Executive summary

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 1 |
| Medium | 3 |
| Low | 2 |

**Top 3 risks:**

1. **Hardcoded JWT signing secret shipped as the default fallback in source** — if the
   `JWT_SECRET_KEY` environment variable is ever unset in a deployed environment, the
   signing key is a fixed, publicly-visible string committed to the repository, letting
   anyone mint valid access/refresh tokens for any user (full authentication bypass).
2. **Same fallback pattern on the database URL and the seed-admin password** — same root
   cause (insecure defaults in `Settings`, no fail-fast if the real env var is missing),
   with a lower but still serious blast radius.
3. **No session/token revocation on logout** — the JWT refresh token is stateless and has
   no server-side blacklist, so a captured refresh token (device theft, log leakage, etc.)
   remains valid for up to 7 days after the user has explicitly logged out.

## Findings table

| # | Severity | Title | File | CWE |
|---|---|---|---|---|
| 1 | Critical | Hardcoded fallback JWT signing secret | `backend/app/core/config.py:12` | CWE-798 |
| 2 | High | Hardcoded fallback DB credentials & seed-admin password | `backend/app/core/config.py:7,23` | CWE-798 / CWE-521 |
| 3 | Medium | No server-side session/token revocation on logout | `backend/app/api/auth.py:70-94` | CWE-613 |
| 4 | Medium | No rate limiting / lockout on login | `backend/app/api/auth.py:55-67` | CWE-307 |
| 5 | Medium | Auth cookies not `Secure` by default | `backend/app/core/config.py:20`, `backend/app/api/auth.py:35-52` | CWE-614 |
| 6 | Low | Login timing side-channel enables user enumeration | `backend/app/services/user_service.py:144-155` | CWE-208 |
| 7 | Low | No security response headers (CSP, X-Frame-Options, HSTS, etc.) | `backend/app/main.py` | CWE-693 / CWE-1021 |

---

## Detailed findings

### 1. Hardcoded fallback JWT signing secret — Critical

**CWE-798: Use of Hard-coded Credentials**

**File:** `backend/app/core/config.py:12`

```python
jwt_secret_key: str = "dev-only-insecure-secret-key-change-me-3f8a1c9d"
```

**Why it's exploitable:** `Settings` is a `pydantic_settings.BaseSettings` that reads
`JWT_SECRET_KEY` from the environment/`.env`, but falls back silently to this literal string
if the variable is absent — there is no startup check that rejects the default in a
non-dev environment. The value is committed to the repository (both here and duplicated in
`backend/.env.example`), so it is effectively public. `backend/app/auth/security.py:41` and
`:65-67` use this key to both sign and verify every access/refresh JWT with `HS256` (a
symmetric algorithm — same key signs and verifies). Anyone who reads the source (i.e.
anyone) can forge a token:

```python
import jwt, uuid, datetime
payload = {"sub": "<any-known-user-uuid>", "type": "access", "roles": ["administrator"],
           "iat": datetime.datetime.utcnow(), "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)}
forged = jwt.encode(payload, "dev-only-insecure-secret-key-change-me-3f8a1c9d", algorithm="HS256")
```

Setting this cookie against a deployment that never overrode `JWT_SECRET_KEY` grants a fully
authenticated session as any user whose id is known/guessed (`get_current_user` in
`backend/app/auth/dependencies.py:17-33` re-fetches the real user/roles from the DB, so the
attacker inherits that account's actual privileges — including `administrator`).
Preconditions: the target deployment must not have set a real `JWT_SECRET_KEY`. This is a
"silent" failure mode — the app runs fine either way, so misconfiguration is easy to miss and
hard to detect from the outside.

**Remediation:**
- Remove the literal default; require `jwt_secret_key` at startup (e.g.
  `jwt_secret_key: str` with no default, or a `model_validator` that raises if the value
  equals the known dev placeholder or is shorter than e.g. 32 bytes).
- Fail fast: raise on app import/startup if the secret is missing or matches the checked-in
  placeholder, rather than degrading to an insecure default.
- Rotate the key in any environment where this default may have been live, which invalidates
  all outstanding tokens.

```python
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    jwt_secret_key: str  # no default — required

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_known_dev_secret(cls, v: str) -> str:
        if v == "dev-only-insecure-secret-key-change-me-3f8a1c9d" or len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be set to a strong, unique value")
        return v
```

**Confidence:** High that the code pattern exists and is exploitable if the env var is unset.
Whether any currently-deployed instance actually has it unset requires manual verification
against real deployment configuration (out of scope for static review).

---

### 2. Hardcoded fallback DB credentials & seed-admin password — High

**CWE-798: Use of Hard-coded Credentials / CWE-521: Weak Password Requirements**

**File:** `backend/app/core/config.py:7,22-23`

```python
database_url: str = "postgresql+asyncpg://ifrit:ifrit@localhost:5432/ifrit"
...
seed_admin_email: str = "admin@ifrit.local"
seed_admin_password: str = "changeme123"
```

**Why it's exploitable:** Same root cause as Finding 1 — these are fallback defaults, not
merely example values in a `.env.example`. `backend/scripts/seed_admin.py:48-56` reads
`settings.seed_admin_password` directly and creates (or reuses, if already present) an
`administrator` + `manager` account with whatever value is configured. If a deployment runs
`uv run python -m scripts.seed_admin` without having set `SEED_ADMIN_PASSWORD`, it creates
`admin@ifrit.local` / `changeme123` — a credential pair published in this very repository —
with full administrative rights. `database_url`'s fallback is lower risk in isolation (it
targets `localhost`), but the pattern of "insecure literal shipped as code default" is the
same and should be fixed the same way; a copy/paste of this settings file into a differently
networked environment (e.g. a shared docker network where `localhost` resolves to the DB
container) would silently connect with `ifrit`/`ifrit`.

**Remediation:**
- Drop the defaults for `database_url` and `seed_admin_password`; require them from the
  environment (`str` with no default, matching the fix pattern in Finding 1).
- Make `seed_admin.py` refuse to run if `SEED_ADMIN_PASSWORD` is unset, rather than silently
  using a value that also appears in source control.
- Consider printing a one-time-use warning (or requiring `--force`) when the seed script runs
  outside a recognized dev environment.

**Confidence:** High.

---

### 3. No server-side session/token revocation on logout — Medium

**CWE-613: Insufficient Session Expiration**

**File:** `backend/app/api/auth.py:91-94` (logout), `backend/app/auth/security.py:63-74` (decode)

```python
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
```

**Why it's exploitable:** `logout` only clears the cookies in the caller's own browser. The
JWTs themselves are stateless — `decode_token` (`security.py:63-74`) validates purely by
signature and `exp`, with no `jti`/denylist check against the database. If a refresh token
cookie was captured before logout (leaked via a proxy/log, a shared/stolen device, a
browser-extension, etc.), it remains fully valid — able to mint fresh 15-minute access tokens
via `POST /api/auth/refresh` — for up to its full 7-day (`refresh_token_expire_minutes =
10080`) lifetime, regardless of the legitimate user having logged out. `docs/requirements/auth.md`
explicitly lists "log out ... to end my session on a shared device" as a user story this
does not fully satisfy for the refresh token.

**Remediation:** Add a minimal server-side revocation mechanism:
- Store a `token_version` (or per-user `jti` allowlist / denylist) column on `User`,
  incremented on logout and checked in `decode_token`/`get_current_user`; or
- Persist issued refresh-token `jti`s in a small table (or Redis) and delete the row on
  logout, checking existence during `/auth/refresh`.

```python
# decode_token / get_current_user, sketch:
if payload.get("ver") != user.token_version:
    raise InvalidTokenError("Token has been revoked")
```

**Confidence:** High that no revocation exists in the current code. Medium on real-world
impact, since it depends on a token actually being captured within its validity window.

---

### 4. No rate limiting / lockout on login — Medium

**CWE-307: Improper Restriction of Excessive Authentication Attempts**

**File:** `backend/app/api/auth.py:55-67`

```python
@router.post("/login", response_model=UserOut)
async def login(
    credentials: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> UserOut:
    user = await authenticate_local_user(db, credentials.email, credentials.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, ...)
```

**Why it's exploitable:** There is no per-IP/per-account throttling, backoff, CAPTCHA, or
lockout anywhere in the request path, and no such middleware/dependency is registered in
`main.py` or listed in `backend/pyproject.toml` (no `slowapi`/`limits`/similar dependency).
An attacker with network access to `/api/auth/login` can attempt unlimited password guesses
against any known `name_id` (email), constrained only by Argon2's per-attempt hashing cost —
which is a server-side cost, not a client-side deterrent, and does not scale down the
attacker's effective throughput across a botnet/distributed attempt.

**Remediation:** Add rate limiting at the login endpoint, e.g. via `slowapi`
(`fastapi`-native, token-bucket per client IP and/or per `name_id`):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login", response_model=UserOut)
@limiter.limit("5/minute")
async def login(...): ...
```

Combine with a per-account failed-attempt counter (temporary lockout after N consecutive
failures) for defense in depth against distributed attempts.

**Confidence:** High.

---

### 5. Auth cookies not `Secure` by default — Medium

**CWE-614: Sensitive Cookie Without 'Secure' Attribute**

**File:** `backend/app/core/config.py:20`, `backend/app/api/auth.py:35-52`

```python
cookie_secure: bool = False
...
response.set_cookie(ACCESS_COOKIE, access_token, httponly=True,
                     secure=settings.cookie_secure, samesite="lax", ...)
```

**Why it's exploitable:** The access/refresh JWT cookies are correctly marked `httponly`
(mitigating cookie theft via XSS) and `samesite="lax"` (reasonable CSRF mitigation), but
`secure` is driven entirely by `COOKIE_SECURE`, which defaults to `False`. The existing code
comment acknowledges this must be set `true` in production, but nothing enforces it — an
operator who forgets (or an environment where `.env` isn't fully populated) will silently
serve session cookies over plain HTTP, exposing them to network-level interception
(on-path attacker, misconfigured TLS-terminating proxy, etc.).

**Remediation:** Invert the default so the secure posture is the fallback, and require an
explicit opt-out only for local dev:

```python
cookie_secure: bool = True  # dev docker-compose / .env.example set this false explicitly
```

Optionally also add a startup assertion that refuses to run with `cookie_secure=False`
unless a separate `environment == "development"` flag is also set, so the insecure
combination can't happen by accident in anything resembling a production config.

**Confidence:** High on the code pattern; actual exposure depends on deployment TLS setup
(needs manual verification of the real deployment's `COOKIE_SECURE` value).

---

### 6. Login timing side-channel enables user enumeration — Low

**CWE-208: Observable Timing Discrepancy**

**File:** `backend/app/services/user_service.py:144-155`

```python
async def authenticate_local_user(db, name_id, password) -> User | None:
    user = await get_user_by_name_id(db, name_id)
    if user is None or not user.is_active:
        return None
    if user.is_sso or user.hashed_password is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
```

**Why it's exploitable:** `docs/requirements/auth.md` explicitly requires "a generic error
message on failed login, so the system doesn't reveal whether an email is registered." The
error message is indeed generic (`auth.py:62-64`), but the code path is not
constant-time: when `name_id` doesn't match any active local user, the function returns
immediately; only when a real local account is found does it run Argon2 `verify()`, which is
deliberately expensive (tens of milliseconds by design). An attacker measuring response
latency for `/api/auth/login` can distinguish "no such active local account" from "account
exists" with a modest number of samples, defeating the stated anti-enumeration goal.

**Remediation:** Perform a dummy hash verification (against a fixed, precomputed Argon2 hash)
on every "user not found / SSO / no password" branch so the response time is uniform:

```python
_DUMMY_HASH = hash_password("not-a-real-password-used-only-for-timing")

async def authenticate_local_user(db, name_id, password) -> User | None:
    user = await get_user_by_name_id(db, name_id)
    if user is None or not user.is_active or user.is_sso or user.hashed_password is None:
        verify_password(password, _DUMMY_HASH)  # burn equivalent time
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
```

**Confidence:** Medium — the vulnerability class and code path are confirmed; real-world
exploitability depends on network jitter and requires statistical sampling, so it is lower
priority than the findings above.

---

### 7. No security response headers — Low

**CWE-693: Protection Mechanism Failure / CWE-1021: Improper Restriction of Rendered UI Layers (Clickjacking)**

**File:** `backend/app/main.py`

```python
app = FastAPI(title="Ifrit API")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router)
```

**Why it's exploitable:** The only middleware registered is CORS. There is no
`Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`,
`Referrer-Policy`, or `Strict-Transport-Security` set anywhere (no such headers in `main.py`,
and per `docs/architecture/infra.md` the production nginx config doesn't exist yet either).
Impact today is limited — the React app doesn't use `dangerouslySetInnerHTML`, `eval`, or
inline event handlers (none found in `frontend/src`), so there's no current first-order XSS
sink this would be compensating for — but the app is served with no clickjacking protection
(could be framed by a malicious site to trick a logged-in user into clicking) and no defense
in depth if an XSS/injection bug is introduced later (e.g. via a future rich-text field or a
third-party widget).

**Remediation:** Add a small headers middleware (or set them in the eventual nginx config
alongside the FastAPI app, per `docs/architecture/infra.md`):

```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response
```

**Confidence:** High that headers are absent; Low severity given no exploitable sink was
found to pair it with today.

---

## Appendix

### Areas reviewed

- **Backend entry points & auth**: `app/main.py`, `app/api/router.py`, `app/api/auth.py`,
  `app/auth/security.py`, `app/auth/dependencies.py`, `app/core/config.py`, `app/core/db.py`.
- **All API routers**: `users.py`, `companies.py`, `currencies.py`, `projects.py`,
  `time_entries.py` — checked for missing/weak authz (`require_roles`/`get_current_user`
  dependency placement), IDOR (object scoping on nested resources), and mass assignment via
  `model_dump()`.
- **All service modules**: `user_service.py`, `company_service.py`, `project_service.py`,
  `time_entry_service.py`, `currency_service.py` — checked for raw SQL/string
  interpolation (none found; all queries use SQLAlchemy Core/ORM with bound parameters),
  business-logic authorization (self-lockout, closed-project read-only, service-line
  eligibility), and privilege checks.
- **All models & schemas**: `models/*.py`, `schemas/*.py` — checked constraints, password
  policy (`PASSWORD_MIN_LENGTH`/`isprintable()`), and field-level validation at the trust
  boundary.
- **Alembic migrations** (`alembic/versions/0001`–`0005`): checked for raw SQL injection
  points (only `sa.text()` with static, non-user-controlled SQL) and any embedded secrets.
- **`scripts/seed_admin.py`**: reviewed as a real (non-test) code path that consumes
  `Settings` defaults directly.
- **Frontend**: `api/client.ts` (fetch wrapper, credential handling, error parsing),
  `providers/AuthProvider.tsx`, `hooks/useAuth.ts`, `components/ProtectedRoute.tsx`,
  `components/RequireRoles.tsx`, `pages/LoginPage.tsx`, `lib/passwordStrength.ts`,
  `components/users/ResetPasswordDialog.tsx`, `App.tsx`, `main.tsx`, `index.html`,
  `vite.config.ts`. Grepped the full `frontend/src` tree for
  `dangerouslySetInnerHTML`/`innerHTML`/`eval`/`new Function`/`document.write`/open-redirect
  patterns (`window.location`, unguarded `navigate()` with external input) — none found;
  all dynamic `navigate()` calls use server-issued UUIDs for same-origin routes.
- **Dependency manifests**: `backend/pyproject.toml`, `frontend/package.json` — reviewed for
  misuse patterns (e.g. missing rate-limiting dependency) rather than a version/CVE audit
  (see "Out of scope" below).
- **Repo-wide secret scan**: grepped for AWS key patterns, PEM private key headers, and
  generic high-entropy `password=`/`secret=`/`api_key=` literals across `.py`, `.ts`, `.tsx`,
  `.json`, `.yml`, `.yaml`, `.toml`, `.ini` files (excluding `node_modules`/`.venv`) — no
  real-looking secrets found beyond the dev placeholders discussed above.

### Reviewed and excluded — dev-only artifacts

- `backend/.env` — real local dev env file; **not committed** (present in `.gitignore`:
  `backend/.env`). Contains only the same generic placeholders as `.env.example`
  (`ifrit`/`ifrit` DB creds, `changeme123`, dev JWT string). Excluded per scope note.
- `backend/.env.example` — template file, generic placeholders only, explicitly documented
  as "copy to `.env` for local development." Excluded per scope note — *except* where the
  same literal values are also hardcoded as in-source defaults in `config.py`, which **is**
  flagged above (Findings 1–2), since that duplication is exactly the "silently ships to
  production" case the scope note calls out.
- `docker-compose.dev.yml` — explicitly documented dev-only Postgres container
  (`POSTGRES_PASSWORD: ifrit`), matches the same placeholder already covered by Finding 2;
  not a separate finding.
- `.debug/debug.sql` — ad hoc local seed-data helper, listed in `.gitignore` under `.debug/`
  (not committed); contains bcrypt hashes for three fixture users. Test/dev fixture, out of
  scope.
- `backend/tests/**`, `backend/tests/factories.py`, `backend/tests/conftest.py` — test
  fixtures/harness. `conftest.py:23` builds a `CREATE DATABASE "{name}"` string via an
  f-string, but the interpolated value comes from `settings.test_database_url` (local trusted
  config, never user input) and only runs in the test harness — not a real SQL injection
  finding.

### Out of scope / not performed

- **Dependency CVE/version audit** (`pnpm audit` / `pip-audit` style scan) — the task asked
  for misuse patterns, not an outdated-version inventory; no such scan was run. Recommend
  running `pnpm audit` and `uv pip list --outdated` / `pip-audit` separately as a
  complementary check.
- **Dynamic testing (DAST)** — this is a static review only; findings around timing
  side-channels (Finding 6) and cookie/header behavior (Findings 5, 7) would benefit from
  confirmation against a running instance.
- **SAML/SSO implementation** — `docs/requirements/auth.md` describes a planned Azure Entra
  ID SAML integration (`python-saml`), but no SSO code exists yet in this tree (only the
  `User.is_sso` flag/branching logic). Nothing to review; flag for a follow-up SAST pass once
  implemented (SAML has its own well-known pitfall class — XML signature wrapping, assertion
  replay, NameID confusion — none of which apply yet).
- **Production Dockerfile / nginx config** — per `docs/architecture/infra.md` these don't
  exist yet in the repo (aspirational/planned only). Finding 7's remediation should be
  revisited once that config exists.
- **CI/CD pipeline** — `docs/architecture/infra.md` marks this as a TODO; no pipeline
  definitions exist in the repo to review.
- **Generated/build artifacts** — `frontend/tsconfig.*.tsbuildinfo`,
  `backend/.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/` excluded as tool caches, not source.


```prompt
Perform a static application security test (SAST) of this codebase and write 
the findings to /docs/sast.md.

Scope:
- Walk the full source tree (exclude node_modules, vendor, build, dist, .git, 
  test fixtures, and generated code).
- Identify the languages/frameworks in use first, then apply checks relevant 
  to that stack (e.g. OWASP Top 10, CWE Top 25).

For each finding, report:
1. Title and CWE ID
2. Severity (Critical / High / Medium / Low) with brief justification
3. File path and line number(s)
4. Vulnerable code snippet
5. Why it's exploitable (attack vector / preconditions)
6. Concrete remediation — a code-level fix, not generic advice
7. Confidence (High/Medium/Low) — flag anything that needs manual verification

Prioritize real, exploitable issues over stylistic nitpicks. Focus areas:
- Injection (SQL, command, template, LDAP, XSS)
- Auth/authz flaws (broken access control, missing checks, IDOR)
- Hardcoded secrets, credentials, API keys
- Insecure deserialization
- Path traversal / arbitrary file read-write
- SSRF
- Cryptographic weaknesses (weak algorithms, improper key/IV handling)
- Insecure dependency usage patterns (not just outdated versions — actual 
  misuse)
- Unsafe use of eval/exec/reflection/dynamic imports
- Missing input validation on trust boundaries (API endpoints, file uploads, 
  webhooks)

Structure /docs/sast.md as:
- Executive summary (counts by severity, top 3 risks)
- Findings table (severity, title, file, CWE) for quick scanning
- Detailed findings (one section per issue, ordered by severity)
- Appendix: files/areas reviewed, and any out-of-scope areas with reasons

Do not modify source code — this is a report-only pass. If the codebase is 
large, prioritize entry points (routes, controllers, API handlers), auth 
logic, and file/data handling code first, then work outward.


Note on dev/example credentials:
This repo contains .env.example files and docker-compose dev configs with 
intentionally hardcoded placeholder passwords/secrets for local development 
only (not used in production).

Do not flag these as findings if they meet ALL of these criteria:
- File is clearly a template/example (e.g. .env.example, .env.sample, 
  docker-compose.dev.yml, docker-compose.override.yml) or is explicitly 
  documented as dev-only
- File is local .env file, not commited to the actual codebase, intended for dev
- The value is a generic placeholder (e.g. "password123", "changeme", 
  "dev-secret", "test") rather than a real-looking credential (long random 
  string, format matching a known provider's key pattern, etc.)
- The same secret is not also referenced or duplicated in production config, 
  CI/CD pipelines, or deployment manifests

DO still flag:
- Real-looking secrets (API keys, tokens, private keys, connection strings 
  with real hostnames) anywhere, even in files named "example" or "sample"
- Dev placeholder credentials that are also hardcoded as defaults in 
  application code (e.g. a fallback value in source if the env var is unset) 
  — this can silently ship the dev secret to production

For anything excluded under this note, list it briefly in the appendix 
under "Reviewed and excluded — dev-only artifacts" with a one-line reason, 
so the exclusion is auditable rather than silent.
```