# Authentication — User Stories

User stories related to authentication and session management. Inferred from
[index.md](index.md) — review and adjust before treating as final. See
[Backend — Authentication & Session Standards](../architecture/backend.md#authentication--session-standards)
for the technical implementation (JWT access/refresh tokens).

## User Stories

- As a user, I want to log in with my email and password so that I can access the app.
- As a user, I want to be logged out automatically when my session expires, so that an idle
  session doesn't stay authenticated indefinitely.
- As a user, I want to explicitly log out, so that I can end my session on a shared device.
- As a user, I want my session to remain active across page reloads (via refresh token) without
  re-entering my credentials every time.
- As a user, I want to see a generic error message on failed login, so that the system doesn't
  reveal whether an email is registered.
- As a user, I want the screens I can access after login to be enforced by my role(s), so that
  I can't view or act on data outside my permissions (see [user.md](user.md) for the
  role/screen matrix).
- As a user, I want to log in via SSO through my organization's Azure Entra ID (SAML 2.0), so
  that I can access the app with my existing corporate identity instead of a separate
  Ifrit-specific password. On successful SAML assertion, the backend issues the same JWT
  access/refresh token pair used for local login, so downstream session handling and
  role-based screen access work identically regardless of login method (see
  [Backend — Authentication & Session Standards](../architecture/backend.md#authentication--session-standards)
  for the `python-saml` dependency this relies on).
- As an administrator, I want to reset a local user's password, so that a user who's locked
  themselves out can get back in without self-service "forgot password" being in scope.
  SSO users have no local password and are not affected — their access is managed entirely by
  the external IdP.

## Session Expiry & Token Refresh

**Status: implemented.** This section describes the mechanism as actually built —
`frontend/src/api/client.ts` (the interceptor itself), `frontend/src/api/sessionEvents.ts` (the
event bridge), and `frontend/src/providers/AuthProvider.tsx` (the subscriber) — rather than a
forward-looking design. It's kept in this narrative form (problem, then the five things a correct
implementation has to handle) because that reasoning is still the best reference for *why* the
code is shaped the way it is, not just *what* it does. See §Notes below for the token lifetimes
(15 min access / 7 day refresh) this mechanism works against, and
[Backend — Authentication & Session Standards](../architecture/backend.md#authentication--session-standards)
for the server-side half (`POST /auth/refresh`) it calls.

### The problem this replaced

Before this was built, `frontend/src/api/client.ts`'s `request()` — the one function every API
call in the app goes through — treated a `401` identically to any other error status (`403`,
`404`, `422`, `500`). Fourteen separate screens/components each independently caught `ApiError`
and rendered `err.message` as if it were a normal, page-specific error (inline text, or in a
couple of places a toast). None of them recognized `401` as meaning "the whole session is dead,"
so a session timeout produced however many independent, redundant error surfaces happened to have
a request in flight at that moment — e.g. a project sheet showing a stale inline "Not
authenticated" message, the timesheet screen popping multiple toasts (it fires two independent
fetches on mount). Separately, because nothing called `POST /auth/refresh`, this didn't just
happen after genuine idle timeout — it happened to every session, active or not, roughly 15
minutes after the last login/page load. The interceptor described below replaces all of this.

### Design overview

One central interceptor, inside `request()` itself (the one chokepoint all API traffic already
passes through), replaces all fourteen screens' independent handling:

1. A request comes back `401`.
2. If the request was to an exempted endpoint (see below), the `401` is thrown as today —
   handled by that endpoint's own existing caller.
3. Otherwise: attempt a silent `POST /auth/refresh`.
   - **Succeeds** → transparently retry the original request once and return its result to the
     original caller. The caller never sees an error at all — from its perspective the request
     just took a little longer.
   - **Fails** (refresh token itself expired/invalid) → the session is genuinely dead. Notify
     the rest of the app (see point 4) and let the original `401` propagate.

This single mechanism is what makes the user story "I want my session to remain active across
page reloads (via refresh token) without re-entering my credentials every time" actually true —
before it existed, that story wasn't, since nothing ever called `/auth/refresh`.

The naive version of "attempt refresh, then redirect" has real gaps if implemented literally as
that one-line description. Five things the implementation has to handle explicitly:

### 1. Concurrent-request de-duplication

This app routinely has multiple requests in flight at once (the timesheet screen alone fires two
independent fetches on mount). If each request's own `401` handler independently called
`/auth/refresh`, an expired token would trigger a burst of simultaneous refresh calls instead of
one. Fix: a single shared "refresh in flight" promise, module-scoped inside `client.ts`. The
first `401` starts it; every other concurrent `401` awaits that same promise instead of starting
its own, then all retry once it resolves.

### 2. Retry-once guard

If the retried request fails again after a successful refresh (refresh succeeded but something
else is still wrong with the retried request), the retry must be marked so it doesn't re-trigger
step 3 of the design overview a second time — otherwise a persistently-failing retried request
could loop.

### 3. Exempting the auth endpoints from the interceptor

`POST /auth/refresh` failing is itself the "give up" signal — if that failure were routed back
through the same "on 401, try refresh" logic, that's an infinite loop calling itself. `POST
/auth/login`'s `401` (wrong credentials) is already documented above as a normal, expected
outcome of that specific call, not a session-expiry signal, and must keep its current inline
handling untouched. `POST /auth/logout` similarly shouldn't trigger refresh-and-retry against
itself. All three must bypass the interceptor and throw `ApiError` directly, exactly as every
endpoint does today.

### 4. Syncing `AuthProvider`'s state — event bridge, not a hard reload

`client.ts` is a plain module with no access to React context — successfully detecting "the
session is dead" there doesn't, by itself, update `AuthProvider`'s `user` state or navigate
anywhere. Two ways to close that gap:

- **(a) Chosen: an event bridge.** A small shared callback registry: `AuthProvider` registers a
  listener on mount (it's rendered inside `<BrowserRouter>` already — see `main.tsx` — so it can
  hold both `setUser(null)` and `useNavigate()`-driven navigation to `/login` in one place);
  `client.ts` invokes that listener once it gives up in step 3 of the design overview. This keeps
  the transition a normal client-side SPA navigation — no full page reload, no lost in-memory
  state anywhere else in the app, no flash of a blank page.
- **(b) Not chosen: a hard `window.location.href = "/login"` redirect.** Simpler to implement
  correctly — a full page reload wipes every piece of JS state for free, so there's no
  registry/subscription lifecycle to get wrong, no risk of a request firing before the listener
  is registered. The trade-off is exactly what (a) avoids: a full page reload on every session
  expiry (brief blank-page flash, slower transition, discards any unrelated in-memory UI state
  elsewhere in the app on the way out) instead of a normal in-SPA navigation.

**(a) is the chosen approach, specifically for SPA compatibility** — the app is built as a
single-page app throughout (React Router client-side navigation everywhere else), and a session
expiry is not a rare-enough event to justify falling back to full-page-reload semantics just for
this one case; it should feel like the same kind of navigation as everything else in the app.
The cost of (a) over (b) is implementation complexity, not user experience: a registry that must
be set up before any request can race it (in practice, `AuthProvider` mounts and subscribes
synchronously before any child component can fire a request, so this is a low but non-zero risk
to keep in mind during implementation, not a fundamental blocker), and exactly one owner of `user`
state (`AuthProvider`) that `client.ts` must never try to duplicate.

### 5. Not double-handling the initial mount-time check

`AuthProvider` already calls `GET /auth/me` once on mount and has its own existing `401`
handling (`setUser(null)`, which `ProtectedRoute` already turns into a redirect on its own — see
`ProtectedRoute.tsx`). This call *should* still go through the same silent-refresh step 3 above
(that's precisely what makes "remain active across reloads" work for a returning user whose
access token expired but whose refresh token is still valid). What it should **not** do is also
fire the event-bridge notification from point 4 when the refresh attempt fails — `AuthProvider`
already handles that outcome itself, correctly, via its own mount-time catch block, and
`ProtectedRoute` already redirects from there. Routing that specific failure through the
event-bridge too wouldn't be incorrect (navigating to `/login` while already about to render a
redirect to `/login` is harmless), just redundant — worth explicitly deciding to skip rather than
leaving as an accidental double-fire.

## Notes

- **Password reset**: not self-service. Administrators reset a local user's password directly.
  There is no "forgot password" flow. SSO users have no local password to reset — access
  changes (disable, revoke, etc.) happen in the IdP.
- **Account creation**: no self-registration. All accounts — local and SSO — are created by an
  administrator (see [user.md](user.md)).
- **Local login coexists with SSO**: enabling SSO for an organization does not remove local
  email/password login as an option for accounts that aren't flagged SSO.
- **SSO identity matching**: an administrator must pre-create the account before a user can log
  in via SSO — there is no auto-provisioning on first login. The SAML `NameID` asserted by the
  IdP is matched against the account's `name_id` column (see [user.md](user.md) for the entity
  detail). `name_id` is not validated/typed as an email address: for a local user it is their
  email, and for an SSO user it's conventionally email-shaped (especially from Azure Entra ID)
  but the IdP does not guarantee that.
- **`is_sso` flag**: an account flagged `is_sso` has no usable local password and cannot log in
  via email/password — only via SAML.
- **IdP scope**: the SAML integration should stay IdP-agnostic in implementation (not
  hardcoded to Azure-specific behavior), even though Azure Entra ID is the primary target.
- **MFA**: not required.
- **Token lifetimes**: confirmed as the implemented defaults — 15 minutes (access) / 7 days
  (refresh); see
  [backend/app/core/config.py](../../backend/app/core/config.py).
