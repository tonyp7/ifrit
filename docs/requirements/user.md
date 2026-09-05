# User — Entity & User Stories

Defines what a `User` is in Ifrit: identity, roles, and role-based screen access. Inferred
from [index.md](index.md) — review and adjust before treating as final.

## Entity

- A user has one or more **roles**: `administrator`, `project_admin`, `project_manager`,
  `consultant`
- **`project_admin`** (renamed from the earlier `manager` — same role, same `projects`-screen
  access, no functional change — renamed specifically to avoid confusion with the new
  `project_manager` below, which is a distinct role with a distinct scope): full access to the
  `projects` screen — creating/editing projects, service lines, and consultant assignments (see
  [project.md](project.md)). Does **not**, by itself, grant `Validation` access — see
  `project_manager` below.
- **`project_manager`**: authority to review and lock/unlock consultants' submitted timesheets
  via the `Validation` sub-destination (see [home.md § Timesheet Menu](home.md#timesheet-menu)
  and [timesheet.md § Validation](timesheet.md#validation)) — **scoped to the specific projects
  that user is assigned to as a project manager**, a per-project assignment (see
  [project.md § Project Managers](project.md#project-managers) — also why this is a deliberate
  exception to the "roles are global" note further down). Holding `project_manager` does not by
  itself grant the `projects` screen, and
  holding `project_admin` does not by itself grant `Validation` — the two are independent axes,
  even though the same person often needs both in practice (e.g. someone who both builds out a
  project's service lines and later locks its consultants' time).
- Multiple roles can be attached to the same user (e.g. a user can be both `project_admin` and
  `consultant`, or `project_manager` and `consultant`)
- **Identity — `name_id`**: the unique column used to match a user for login (see
  [auth.md](auth.md)).
  - For a local (non-SSO) user, `name_id` is their email address.
  - For an SSO user, `name_id` is the SAML `NameID` asserted by the IdP — conventionally
    email-shaped, but not guaranteed to be a valid/well-formed email, so it must not be
    typed/validated as one.
- **`is_sso`** (boolean): flags whether the account authenticates via SSO. An `is_sso` user has
  no local password and cannot use email/password login — SAML only.
- **`theme_preference`**: `light` | `dark` | `system` (default `system`). Set from the profile
  menu and persisted server-side so it follows the user across devices/sessions — see
  [home.md](home.md#appearance) for the full behavior.
- Exact remaining attribute list (name, etc.) is TBD

## Role → Screen Access

| Role               | Screens                                                                 |
| ------------------ | ------------------------------------------------------------------------ |
| `consultant`       | `timesheet` (own)                                                          |
| `project_admin`    | `timesheet` (own) + `projects`                                                  |
| `project_manager`  | `timesheet` (own) + `Validation` sub-destination (scoped to assigned projects — see below) |
| `administrator`    | `timesheet` (own) + `configuration`                                             |

**`projects` is granted by the literal `project_admin` role only — not inferred from
`administrator`.** An `administrator` who doesn't also separately hold `project_admin` does not
get the `projects` screen (nav icon not shown). This is why the dev-only seed script
(`scripts/seed_admin.py`) assigns the seeded default user **both** `administrator` and
`project_admin` — an `administrator`-only bootstrap account would have no way to reach `projects`
to verify or manage anything there.

`configuration` is the master-data management area: `companies` and `users` today, with room
for other master data later (all still administrator-only). It's one entry point grouping
multiple screens/entities — see [home.md](home.md) for how this is exposed in navigation.

`timesheet` also behaves differently depending on role, despite being one entry in the table
above: a `consultant`, an `administrator`, or a `project_admin` — any of these, so long as they
don't *also* hold `project_manager` — goes straight to their own timesheet. A `project_manager`
(the literal role — not inferred from `administrator` or `project_admin`) additionally gets a
`Validation` sub-destination for reviewing/locking consultants' submitted timesheets, restricted
to the specific projects that user is assigned to as a project manager (see
[project.md § Project Managers](project.md#project-managers) for that assignment mechanism) —
see [home.md § Timesheet Menu](home.md#timesheet-menu) for how this is exposed in navigation, and
[timesheet.md](timesheet.md) for the timesheet screen itself.

Since a user can hold multiple roles, their visible screens are the union of the screens granted
by each role they hold — confirmed by the `administrator` + `project_admin` combination the seed
script relies on to give the bootstrap account full access (see `scripts/seed_admin.py`).

## User Stories

- As an administrator, I want to create, edit, and deactivate user accounts, so that I control
  who has access to the app.
- As an administrator, I want to assign one or more roles to a user, so that their access
  matches their responsibilities.
- As a consultant, I want to see only the `timesheet` screen, so that I'm not exposed to
  project/company data I don't need.
- As a project_admin, I want to see the `timesheet` and `projects` screens, so that I can manage
  the projects I'm responsible for in addition to my own timesheet.
- As a project_manager, I want to review and lock/unlock timesheets for consultants on the
  projects I'm assigned to, so that I can freeze submitted time once it's ready for
  billing/payroll, without being able to affect projects I'm not responsible for.
- As an administrator, I want to see the `timesheet` and `configuration` screens, so that I can
  manage master data (companies, users) as well as submit my own timesheet — `projects` is not
  included unless I separately also hold the `project_admin` role.
- As an administrator, I want to create a new user account (local or SSO) via a clearly visible
  "+" action on the users list, so that provisioning an account is a single obvious step —
  account creation is always administrator-initiated, never self-service (see
  [auth.md](auth.md)).
- As an administrator, I want to edit an existing user's name and roles, so that I can correct
  records or adjust access as responsibilities change.
- As an administrator, I want to duplicate an existing user as the starting point for a new one,
  so that provisioning several similar accounts (e.g. a batch of new consultants) doesn't mean
  re-picking the same roles every time.
- As an administrator, I want to deactivate a user, understanding that this preserves
  referential integrity (`is_active = false`) rather than removing the row, so that a
  deactivated user's historical data (e.g. past service line assignments) stays intact.
- As an administrator, I want to reset a local user's password from the same screen where I
  manage their account, so that I don't need a separate tool for a closely-related action (see
  [auth.md](auth.md)).
- As an administrator, I want to quickly search the users list by name or login identity, so
  that I can find a specific account without scrolling through all of them.

## Users List Screen

The `users` screen under `configuration` (see [home.md](home.md#navigation)) — deliberately
consistent with the [Companies List Screen](company.md#companies-list-screen) pattern, not a
bespoke layout:

- **Header**: shadcn/ui's native Data Table filter component, filtering by `full_name` and
  `name_id` as the administrator types (both are realistic ways to look someone up), and a
  **`+`** button that opens the create-user flow.
- **Columns**: `full_name`, `name_id` (login identity), `roles` (each held role shown as its own
  small `Badge` chip, not a raw array), login method (`Local` / `SSO`, derived from `is_sso` —
  shown as a label, never the raw boolean), status (`is_active`, an Active/Inactive indicator —
  same principle as Company's status column, not a raw boolean), then a trailing actions column.
- **Row actions**: an **`…`** button opens a dropdown with, in order: `Edit`, `Duplicate`,
  `Reset Password`, a separator, then `Delete`.
  - `Reset Password` reuses the already-implemented `POST /users/{id}/reset-password` endpoint
    (administrator-only, rejects SSO targets with a 400) — opens a small dialog to set a new
    password, subject to §Password Policy below, including its live strength meter. Only enabled
    for `Local` rows; disabled (or hidden) for `SSO` rows, so the UI proactively reflects a
    constraint the backend already enforces rather than letting the admin hit a raw error.
  - `Delete` is styled destructive and requires a confirmation dialog, like every destructive
    action app-wide (see [frontend.md](../architecture/frontend.md#destructive-actions)). Same
    one-way soft-deactivation semantics as Company — `is_active = false`, no reactivate UI yet.
- **Pagination**: 50 users per page, `Previous`/`Next` controls — same as Company, no
  jump-to-page or page-number list.

## User Form (Create / Edit / Duplicate)

`New`, `Edit`, and `Duplicate` all open the same form, mirroring
[Company Form](company.md#company-form-create--edit--duplicate)'s structure:

- **`New`**: blank form.
- **`Edit`**: pre-filled with the source user's current values.
- **`Duplicate`**: pre-fills `roles` and the `is_sso` `Switch` state from the source user —
  `name_id`/`full_name` are deliberately left **blank**, not copied, since `name_id` must be
  unique and copying it verbatim would just be rejected on save (the same class of issue
  company.md flags for its own `Duplicate` — see
  [Company Form](company.md#company-form-create--edit--duplicate)). One-at-a-time only — no
  batch/"create N similar accounts" functionality, matching Company's `Duplicate`.
- The form stays close to the data model, exposing:

  | Field              | Input                                             | Notes                                                                                                                                                                                                                                                                                                    |
  | ------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | `full_name`           | Text input                                            | Required                                                                                                                                                                                                                                                                                                       |
  | `name_id`               | Text input                                              | Required, must be unique — a save-time validation error, not a live-as-you-type check                                                                                                                                                                                                                          |
  | `is_sso`                  | shadcn/ui `Switch`, labeled "SSO User"                       | Off by default on `New` (a new user is local unless deliberately switched on). Mutable on `Edit`, not just at creation — see "Toggling `is_sso` on `Edit`" below for what happens in each direction. See [auth.md](auth.md)'s `is_sso` flag                                                                                                                                                                                                              |
  | initial password           | Password input                                              | Shown whenever the effective state is local (`is_sso` off) **and** there's no usable password yet: on `New`, and on `Edit` when switching an existing SSO user back to local. Subject to §Password Policy below, including its live strength meter. Hidden whenever `is_sso` is on. Also hidden on `Edit` for a user who's already local and stays local — changing an already-local user's password goes through the `Reset Password` row action, not this form |
  | `roles`                       | Checkbox group: `administrator` / `project_admin` / `project_manager` / `consultant`   | **Required — at least one role must stay checked**, a save-time validation error otherwise (no role-less accounts, since one with zero roles could log in but reach zero screens). On `New`, `consultant` is pre-checked by default — the other three are opt-in. Multiple selectable. A plain checkbox list is the right call here — unlike the Service Line consultant picker in [project.md](project.md#service-lines), which specifically needed a searchable combobox because that list can grow to hundreds of entries, the role set is fixed at 4                            |

  `theme_preference` and `is_active` are **not** exposed on this form. `theme_preference` is
  self-service only, set from the user's own profile menu (see
  [home.md § Appearance](home.md#appearance)) — never admin-editable. `is_active` is only ever
  set via the `Delete` row action, same as Company.
- **Toggling `is_sso` on `Edit`**: mutable after creation, in both directions —
  - **Local → SSO**: on save, the user's password is cleared server-side (`hashed_password` set
    to `NULL`) — not just hidden, permanently unrecoverable. Before saving, a shadcn/ui `Alert`
    appears directly under the `Switch`:

    > **"Changing this user to SSO will remove this user's existing password. The user's current
    > password will not be recoverable and will need to be re-initialized if it is switched back
    > to a local user. Proceed with caution."**
  - **SSO → local**: the initial password field reappears and becomes required — the account has
    no usable password until one is set, so the form can't be saved without filling it in.
- **Footer actions**: a **`Save`** button and a separate **`Close`** button in the bottom-left
  corner, positioned at the bottom of the whole form — same convention as the Company form.

### Password Policy

Applies everywhere a password is set for a local (`is_sso = false`) user — the `New` form's
initial password field, `Edit`'s reappearing password field (SSO → local), and the `Reset
Password` row action's dialog. Not applicable to SSO users, who have no local password at all.

- **Length**: minimum 12 characters, maximum 255.
- **Character set**: all printable characters are allowed, including spaces and full Unicode
  (accented letters, non-Latin scripts, emoji). The only characters rejected are Unicode control
  characters (category Cc — tab, newline, null byte, etc.); a plain space (`U+0020`) is
  explicitly allowed despite technically being a control-adjacent character in some narrower
  definitions of "printable."
- **Hashing**: Argon2id via `argon2-cffi`, not `bcrypt` — bcrypt only uses the first 72 *bytes*
  of input, which a 255-character/full-Unicode password can easily exceed (multi-byte UTF-8
  characters, especially emoji, make this worse), so this length/character-set policy would be
  silently unsafe (or outright broken, depending on the bcrypt version) under the previously
  documented `bcrypt` choice — see [backend.md](../architecture/backend.md#core-dependencies).
- **Enforced strictly server-side**, not just in the UI — posting a non-compliant password
  directly to the API (bypassing the form) must be rejected the same way, on both the not-yet-built
  create-user endpoint and the existing `POST /users/{id}/reset-password` (whose `min_length`
  must move from its current `8` up to `12`, plus a new `max_length=255` and the character-set
  check — see `PasswordResetRequest` in `backend/app/schemas/user.py`).
- **Exemption**: the dev-only seed script (`scripts/seed_admin.py`) bypasses this entirely — it
  inserts its seeded user directly via the DB session, not through any validated API path. Its
  current default password (`changeme123`, from `SEED_ADMIN_PASSWORD`) is 11 characters, under
  this policy's 12-character minimum — that's expected and fine precisely because the seed path
  never goes through the validation this policy describes; it's not evidence the policy is
  unenforced elsewhere.

**Strength meter (UI)**: displayed live under every password-entry field described above (not
just on `New`) —

- Powered by `@zxcvbn-ts/core` (see
  [frontend.md § Core Dependencies](../architecture/frontend.md#core-dependencies) — not the
  original unmaintained `zxcvbn` package).
- Two elements together: a shadcn/ui `Progress` bar (`score / 4` as its percentage — 0%, 25%,
  50%, 75%, 100%) and a shadcn/ui `Badge` reading the follow label:

  | Score | Label       |
  | ------- | ------------- |
  | 0         | Very Weak       |
  | 1         | Weak              |
  | 2         | Fair                |
  | 3         | Good                  |
  | 4         | Strong                  |

- Recomputes on every change to the field's value, regardless of how the value changed —
  keystroke, paste, or any other source — so it must be driven off the controlled input's actual
  value (e.g. a React `onChange`/`value`-watching effect), not a keydown/keyup listener that
  would miss paste or programmatic changes.
- **Resolved: purely advisory, permanently** — this is a strength *indicator*, not an
  additional hard gate, and stays that way. The 12–255/character-set rule above is the entire
  save-time enforcement; a `Very Weak` password that still meets length and character-set
  requirements is never blocked from saving by the meter itself, no minimum score required.

## Notes
- Roles are global, NOT scoped per-project/per-company — **with one deliberate exception**:
  holding `project_manager` is a global eligibility flag (same pattern as `consultant`, which
  gates eligibility for Service Line assignment — see [project.md § Service Lines](project.md#service-lines)),
  but that role's actual *authority* is scoped per-project via a separate assignment — see
  [project.md § Project Managers](project.md#project-managers).
- User identity is `name_id` (see Entity above), not necessarily an email address. It must be
  unique.
- User should be soft-deleted to preserve referential integrity through the is_active flag

## Open Questions

- **Resolved — self-lockout**: an administrator can never reduce their **own** administrative
  standing, full stop — this isn't scoped to "the last remaining administrator," it applies
  regardless of how many other administrators exist. Blocked in both places it could happen:
  - **`Delete`** (deactivate) on your own user row.
  - **`Edit`** → unchecking your own `administrator` role, whether or not other roles/checkboxes
    also changed in the same save.

  Both are rejected outright — save-time validation error on `Edit`, and the `Delete`
  confirmation dialog's confirm action itself fails — rather than silently ignored or partially
  applied. Doing either to *another* administrator's account is unaffected; only acting on your
  own account this way is blocked. Error message (toast, matching this app's existing
  action-failure pattern — see [frontend.md § User Feedback](../architecture/frontend.md#user-feedback-toasts)):

  > **"You can't remove your own administrator access — ask another administrator to make this
  > change for you."**
- **Resolved — zero-assignment state (the user side)**: a user can hold `project_manager` while
  assigned to zero projects (see [project.md § Project Managers](project.md#project-managers) for
  the project side of this, where it's also a valid state). The `timesheet` nav icon's dropdown
  still shows the **Validation** entry (not hidden), and the Validation screen itself renders
  empty — no special-casing to hide the entry point. Not yet implemented (the Validation screen
  itself doesn't exist yet — see [timesheet.md § Open Questions](timesheet.md#open-questions)),
  but decided ahead of building it.
- **Resolved — self-lock**: yes. If a `project_manager` is also a `consultant` on the same
  project (an already-supported multi-role combination, same pattern as today's `project_admin` +
  `consultant`), they can lock/unlock their own cells — no restriction, kept deliberately simple
  rather than adding a carve-out for self-assigned work. Not yet implemented, same caveat as
  above — see [timesheet.md § Open Questions](timesheet.md#open-questions).
- **Resolved — consultant-picking scope on Validation**: a `project_manager` can only see/lock
  consultants assigned to service lines on projects where *they themselves* are assigned as
  project manager (not every consultant system-wide) — now fully specified, including how it's
  surfaced in the Validation UI, in [timesheet.md § Validation](timesheet.md#validation).
