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
