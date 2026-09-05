# Project — Data Model & User Stories

Defines what users see under the `Projects` navigation menu item, the `Project` entity and its
relationship to companies, service lines, and users, and its CRUD interactions. Inferred/drafted
— review and adjust before treating as final. See also [company.md](company.md),
[user.md](user.md).

The schema in this document (§Project Schema) is this doc's description of the model; the
actual implemented tables (Ifrit's naming conventions, exact types, constraints) live in
[database.md](../architecture/database.md#tables) and are the authoritative source once
implemented.

## User Stories

Per [user.md](user.md#role--screen-access), only the `project_admin` role has access to the
`projects` screen by default — `administrator` does not, unless that specific user also
separately holds `project_admin` (e.g. the dev-seeded default admin, which is assigned both).
Stories below say "project_admin" since that's the actual gating role, not just the primary
persona. (`project_admin` is a rename of the earlier `manager` role — same access, no functional
change — done to avoid confusion with the newer `project_manager` role, which governs
`Validation`/timesheet-locking access instead of this screen; see
[user.md § Entity](user.md#entity).)

- As a project_admin, when I land on the project page, I want to see a list of all projects, so
  that I can view or edit existing projects.
- As a project_admin, when I land on the project page, I want a new-project button, so that I can
  create a new project.
- As a project_admin, I want to create a project by selecting any company as the client, a
  vendor-flagged company as the vendor, an invoicing currency, and a project type, so that the
  project is correctly set up for billing.
- As a project_admin, I want to add service lines to a project, each with a quantity and unit
  price, so that I can define the billable scope of work.
- As a project_admin, I want to assign consultants to a service line, so that they can log
  time/work against it.
- As a project_admin, I want to view and edit the projects I'm responsible for, so that I can
  keep project data current.
- As a project_admin, I want to assign one or more `project_manager`s to a project, so that
  there's someone with authority to review and lock/unlock consultants' submitted timesheets for
  it — see [Open Questions](#open-questions) below; this assignment mechanism is not yet
  specified.
- As a consultant, I want to log time (via the `timesheet` screen) against a service line I'm
  assigned to, so that my work is tracked and billable.
- As a consultant assigned to more than one service line on the same project, I want each line
  to optionally have a name, so that I can tell them apart when picking which one to log time
  against (see [timesheet.md](timesheet.md)).

## Projects List Screen

The `projects` screen (see [home.md](home.md#navigation)). A Data Table:

- **Header**: presumed to follow the same pattern as the Companies list — shadcn/ui's native
  Data Table filter component and a **`+`**/`New` button that opens the create-project flow —
  not explicitly restated here; see [company.md](company.md#companies-list-screen).
- **Columns**: `name`, `status`, `client`, `project_type`, `created_at` (creation date) are
  shown by default. `vendor` is not shown by default, but is toggleable via the Data Table's
  built-in column-visibility "Columns" button (shadcn/ui's standard Data Table feature) — the
  first place in the app using that particular feature; see [frontend.md](../architecture/frontend.md)
  when documenting the pattern for reuse elsewhere.
- All columns are sortable, using the Data Table's out-of-the-box (TanStack) sorting — no custom
  sort logic.
- Default sort on landing: `created_at` descending.
- **Row actions**: an **`…`** button opens a dropdown menu with `Edit`, `Duplicate`, then
  (presumed, matching the Companies list and [frontend.md](../architecture/frontend.md#destructive-actions))
  a separator, then `Delete`, styled destructive. `Delete` sets a dedicated soft-delete flag —
  `is_active` (see §Project schema below) — **separate from** `status`. `closed` is a legitimate,
  independent lifecycle state, not a stand-in for deletion: a project can be `closed` and still
  active (`is_active = true`, just no longer open for work), or deleted (`is_active = false`)
  regardless of its `status`. Like every destructive action app-wide, `Delete` must show a
  confirmation dialog. Unlike `Company` (which keeps deactivated rows visible with an
  Active/Inactive badge), soft-deleted (`is_active = false`) projects are **filtered out of the
  list entirely** — a deliberate divergence from the Company pattern, not an oversight. There is
  currently no UI to reactivate a deleted project, same as Company.
- **Pagination**: 50 projects per page, with `Previous`/`Next` controls — no jump-to-page or
  page-number list.

## Project Form (Create / Edit / Duplicate)

Presumed, by analogy with [company.md](company.md#company-form-create--edit--duplicate), that
`New`, `Edit`, and `Duplicate` all open the same form, with `Save`/`Close` footer actions at the
bottom — not explicitly restated in the original draft; confirm before implementing.

**Responsive layout**: the header fields (`Name`, `Vendor`/`Client`, `Invoicing currency`/
`Project type`, `Status`/`Total value`) stack one per line on mobile and pair up two-per-line
from the `sm` breakpoint up — per this project's mobile-first rule (see
[frontend.md](../architecture/frontend.md#mobile-first)), not a fixed two-column grid at every
width. This applies only to these header fields — the Service Lines table below (see §Service
Lines) is unaffected, since it's already a horizontally-scrollable Data Table, not a field grid.

- **`New`**: blank form.
- **`Edit`**: pre-filled with the source project's current field values. For a `closed` project,
  `Edit` still opens the same form, but in a **read-only state** — fields greyed out per standard
  UI practice (disabled inputs, no `Save`), rather than hiding/disabling the `Edit` action itself
  on the list. **`status` is the one exception**: it stays editable even in this read-only state,
  specifically so a `closed` project can always be moved back to `active`/`draft` — otherwise a
  project could get soft-locked into `closed` with no way out (see §Status enum below).
- **`Duplicate`**: copies everything — header fields (vendor/client/currency/type) **and** all
  service lines with their consultant assignments — but the new project is always created with
  `status = draft`, regardless of the source project's status, so every copied field/line starts
  fully editable (see §Status enum and the Service Line edit/delete rules below). Unlike `Edit`,
  `Duplicate` is **not** affected by the source project being `closed` — it always produces a
  fresh, fully-editable `draft` copy. `is_active` is not copied either — same as `Company`'s
  `Duplicate` (see [company.md](company.md#company-form-create--edit--duplicate)), it's not one
  of the exposed form fields, so a duplicated project is never created pre-deleted.

### Service Lines

Presumed, by analogy with Company's Party Identifiers/Addresses sub-tables (see
[company.md](company.md#party-identifiers)), to be a Data Table of the project's `Service Line`
rows (§Service Line schema below) shown as a sub-section within the Project form, with a
**`+`** button opening an add modal and a **`…`** row action for `Edit`/`Duplicate`/`Delete`.

**Columns, in order**: `Name`, `Quantity`, `Unit` (the `uom` label), `Unit price`, `Value`,
`Consultants`, then the **`…`** actions column — `Name` is newly added ahead of the
already-established columns, not a replacement for any of them. `Name` is shown even when empty
(blank cell) — see §Service Line entity below for why the field exists (disambiguating multiple
lines on the same project when logging time — see [timesheet.md](timesheet.md)). `Value` is each
line's calculated value (see §Calculated values below); the Project Form itself also shows the
project's `total value`.

The `Consultants` cell lists each assigned consultant's name **one per line, not
comma-separated** — a comma-joined list becomes hard to read once more than a couple of
consultants are assigned to the same line. Concretely: each name is its own block element (one
`<div>` per consultant) inside the cell, not a single string joined with an embedded `\n` — a
literal newline character doesn't render as a line break in HTML without extra `white-space`
CSS, so joining on `", "` vs `"\n"` looks identical unless the elements are actually split.
**Known divergence**: the current implementation (`ServiceLinesTable.tsx`) still does
`line.users.map((u) => u.full_name).join(", ")` — genuinely comma-separated — which this section
already called out as wrong before this note existed; not yet fixed.

A not-yet-saved (`New`) project's Service Lines table needs the same "auto-save on first child
row" handling as Company's Party Identifiers/Addresses: a `Service Line` can only attach to a
persisted `project_id`, so clicking **`+`** on a not-yet-saved project (1) validates the form's
required fields, showing an inline error and stopping if invalid, (2) if valid, silently saves
the project first — same effect as `Save` — to obtain its `project_id`, then (3) opens the
add-service-line modal as normal. For an already-saved project, **`+`** just opens the modal
directly. See [company.md](company.md#creating-a-new-companys-identifiersaddresses-auto-save)
for the full step-by-step this mirrors.

Consultant assignment (`Service Line.users`) is to happen from within the service
line's own add/edit modal, picking from active `consultant`-role users

**Add/Edit Modal** 
The add/edit modal exposes the same fields the entity has, per this app's "stay close to the
data model" convention (see
[company.md](company.md#company-form-create--edit--duplicate)): `Name`, `Quantity`, `Unit`
(the `uom` selector), `Unit price`, and the `Consultants` picker. `Duplicate` (both at the
row level and via a full Project `Duplicate`) copies `name` along with every other field —
see §Project Form above.

Title of the Modal: "Add service line" in case of an addition/duplicate, "Edit service line" in case of edit
The modal has only one implementation and support all use cases. It only differs on how data is prefilled or not 
inside the modal.
- Line 1: Name - Input Name
- Line 2: 
  - 1st Column Quantity / Input Quantity (only accepts numbers and decimal point input, silently strip any non valid input)
  - 2nd Column Unit / Combobox selector with UOMs as per the model (Days, Hours, EA)
- Line 3: Unit Price / Input Unit price (only accepts numbers and decimal point input, silently strip any non valid input)
- Line 4: Consultants / searchable multi-select combobox, not a plain checkbox list — a plain
  list of checkboxes breaks down once a company has hundreds of consultants to pick from. A
  trigger button ("Select consultants…") opens a `Popover` containing a `Command` palette: a
  search input (autofocused, filters as you type) above the list of active `consultant`-role
  users. Selecting a user adds them to the assignment and shows them as a removable chip
  (`Badge`, with an `×` to unassign) below the trigger; the popover stays open so multiple
  people can be added in one pass. New dependencies: `cmdk` (powers shadcn's `Command`) and
  `@radix-ui/react-popover` (already covered by the blanket `@radix-ui/*` Core Dependencies
  entry in [frontend.md](../architecture/frontend.md#core-dependencies) — only `cmdk` needs a
  new line there).
  **Search is server-side, not a client-side filter over one pre-fetched list**: given the
  "hundreds of consultants" scaling concern this field exists to address, fetching every active
  consultant up front stops being viable at that size. Each keystroke (debounced) queries the
  existing users-list endpoint (`GET /users`, see `list_users_endpoint` in
  `backend/app/api/users.py`), extending its current `role` filter with a `search` param (name
  substring match) — the endpoint's shape doesn't otherwise change. This is a divergence from
  the currently-implemented picker, which calls `listUsers({ role: "consultant" })` once on open
  and filters nothing itself.
  The popover closes the same way any Radix `Popover` does — click-outside or `Escape` — no
  explicit "Done" button.
Bottom of the form: A Save button

**Edit/delete rules by project status** (see §Status enum below):

- **`draft`**: service lines can be freely added, edited, and removed.
- **`active`**: existing lines can be edited, and new lines can be added. A line can be
  **deleted only if no time has been logged against it** — an orphan line (e.g. one added by
  mistake and never used) is safe to remove without compromising any already-logged time; a
  line with logged time attached is not deletable, only editable.
  **TODO — not yet implementable**: this check depends on time-entry data that doesn't exist
  yet (no `timesheet.md`/time-entry concept — see [timesheet.md](timesheet.md#open-questions)).
  Until timesheeting exists, deletion of a service line on an `active` project is allowed
  unconditionally (i.e. behaves like `draft`); switch to the conditional check once time entries
  exist to check against.
- **`closed`**: fully read-only — no add, edit, or delete on service lines (or the project's
  header fields — see §Status enum below).

## Project Schema

Two entities:

1. **Project** — the billing engagement itself: vendor/client companies, currency, type,
   status, and its service lines.
2. **Service Line** — one-to-many billable line items belonging to a project, each with its own
   quantity/unit/price and assigned consultants.

```
Project (1) ──< Service Line (N)
Service Line (N) ──< User (N)   [many-to-many: consultants assigned to a line]
```

### 1. Entity: `Project`

| Field                 | Type                 | Required | Notes                                                                                                                                                                                                          |
| ---------------------- | ---------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `project_id`             | UUID / surrogate key   | Yes          | Primary key                                                                                                                                                                                                       |
| `name`                     | string                 | Yes          | No uniqueness constraint — two projects may share the same `name`. Assumed non-empty (not explicitly stated).                                                                                                                    |
| `vendor`                     | FK → Company           | Yes          | Must reference a company with `is_vendor = true` (see [company.md](company.md))                                                                                                                                      |
| `client`                      | FK → Company           | Yes          | Any company, `is_vendor` or not — every company is implicitly usable as a client. Can be the same company as `vendor` (inter-company/self-billing) — intentional, not a bug to guard against.                          |
| `invoicing_currency`            | FK → Currency               | Yes          | ISO 4217 alpha code (`currencies.alpha_code`); must reference a currency with `is_enabled = true` — see §Currency below                                                                                                                          |
| `project_type`                    | enum                    | Yes          | See §Project Type enum below                                                                                                                                                                                             |
| `status`                            | enum                    | Yes          | See §Status enum below. Default presumed `draft` (listed first) — not explicitly stated                                                                                                                                 |
| `is_active`                           | boolean                 | Yes          | Soft-delete flag, same pattern as `Company`/`User` (default `true`) — set to `false` by the `Delete` action on the projects list. **Independent of `status`**: `closed` is a real lifecycle state, not a synonym for deleted; a project can be `closed` and still `is_active = true`. Not exposed on the Project form — only ever set via `Delete`, same as `Company.is_active` (see [company.md](company.md#1-entity-company)). |
| `created_at`                         | timestamp               | Yes          | Record creation                                                                                                                                                                                                            |
| `updated_at`                          | timestamp               | Yes          | Record last modified                                                                                                                                                                                                        |

#### Validation rules

- `name` must not be empty. No uniqueness constraint, globally or per vendor/client pair.
- `vendor` must reference a company with `is_vendor = true`.
- `invoicing_currency` must reference a `currencies` row with `is_enabled = true` (see
  [database.md](../architecture/database.md#currencies)).
- No other field-level rules specified beyond the `status` transition rules in §Status enum
  below.

#### Status enum

| Value    | Label   | Description                          |
| ---------- | --------- | --------------------------------------- |
| `draft`     | Draft     | Initial State. Service lines are freely editable/addable/removable. |
| `active`     | Active    | Time can be logged (via the `timesheet` screen, see [home.md](home.md#navigation)) against the project's service lines. Existing service lines can be edited, and new ones added; a line can only be deleted if it has **no** time logged against it — see Service Lines above. Deletion is unconditional for now, pending timesheeting ([timesheet.md](timesheet.md#open-questions)). |
| `closed`      | Closed    | A genuine lifecycle state, independent of the `is_active` soft-delete flag (see §Project entity above) — not a delete/archive mechanism. **Read-only**: nothing on the project — header fields or service lines — can be edited, added, or deleted once `closed`. |

**Transition rules**: unrestricted — a project can move from any status to any other status
directly (no enforced workflow, e.g. `active` → `draft` or `closed` → `active` are both valid).
`status` is primarily a filtering/sorting aid and a switch for the edit rules above, not a strict
lifecycle gate. No role restriction beyond having `project_admin` access to the screen itself
(see [user.md § Role → Screen Access](user.md#role--screen-access) — `administrator` alone does
not grant it). Because of this, `status` is deliberately the **one field exempted** from
`closed`'s read-only form (see Project Form above) — a project must always be movable out of
`closed`, so it can never get soft-locked with no way to change it back.

#### Project Type enum

| Value                 | Label            | Description                                                                                   |
| ----------------------- | ------------------ | ------------------------------------------------------------------------------------------------- |
| `time_and_material`       | Time & Material    | Billed on actual `quantity` × `unit_price` recorded on service lines, no upper bound                |
| `fixed_price`               | Fixed Price         | Still `quantity` × `unit_price` on each service line. A `fixed_price` project billing can be independent from the project line tracking. (to be implemented in billing)  |
| `capped_tm`                   | Capped T&M          | Time & Material billing with an upper cap. No explicit cap-amount field on the project — `project_type` matters for downstream billing logic (not yet implemented), not for the project record/form itself.                |

`Label` here follows the same value → label display convention as `id_type`/`address_type` in
[company.md](company.md#21-id_type-enum) — proposed, not confirmed in the original draft.

#### Currency

- The currency list is a fixed list backed by the `currencies` database table — see
  [database.md](../architecture/database.md#currencies).
- Only currencies with `is_enabled = true` are selectable/visible in the currency picker.
- The currency name (e.g. "US Dollar") is translated like every other label, per this project's
  internationalization rules (see [frontend.md](../architecture/frontend.md#internationalization-i18n)).

### 2. Entity: `Service Line`

| Field                | Type                | Required | Notes                                                                                                                                     |
| ---------------------- | --------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `service_line_id`         | UUID / surrogate key    | Yes          | Primary key                                                                                                                                    |
| `project_id`                | FK → Project            | Yes          |                                                                                                                                                    |
| `name`                        | string — `VARCHAR(255)`  | No          | Free text. No uniqueness constraint (not even per-project) and no format requirement — may be left empty. Exists purely so a consultant assigned to more than one service line on the same project can tell them apart when picking which one to log time against (see [timesheet.md](timesheet.md)) — not used anywhere else (billing, calculations, etc. are unaffected by it). |
| `quantity`                    | decimal — `NUMERIC(12, 5)` | Yes      | Does not depend on `uom` — always the same decimal shape (e.g. `7.50000`) regardless of unit type                                                    |
| `uom`                           | enum                    | Yes          | See §UOM enum below                                                                                                                                  |
| `unit_price`                      | decimal                 | Yes          | Denominated in the parent project's `invoicing_currency` — confirmed there is no separate per-line currency field                                            |
| `users`                             | User[] (0..N)            | No           | Consultants assigned to log time against this line — many-to-many, presumably a join table like `user_roles` (see [database.md](../architecture/database.md)) |
| `is_active`                          | boolean                 | Yes          | Soft-delete flag (default `true`) — see §Validation rules below for what sets it and how it's queried                                                          |

#### Validation rules

- `name` has no required format and no uniqueness constraint — two lines on the same project
  (or different projects) may share a name, or both be empty.
- `Delete` is a **soft delete**: it sets `is_active = false` rather than removing the row —
  same pattern as `Company`/`Project`. There is no UI to recover a soft-deleted line. Every
  query that lists a project's service lines (the Service Lines table, `total value`
  calculation, etc.) must filter to `is_active = true`; this should be an indexed lookup (e.g.
  an index on `(project_id)` — or a partial index `WHERE is_active`, matching the pattern used
  for `addresses`' partial unique index in [database.md](../architecture/database.md#addresses))
  rather than a full scan per project. Like every destructive action app-wide, `Delete` needs a
  confirmation dialog (see [frontend.md](../architecture/frontend.md#destructive-actions)) — not
  restated per-action elsewhere in this doc, but applies here too.
- On an `active` parent project, `Delete` is blocked once **any time has been logged** against
  the line — editing remains allowed regardless. **Until timesheeting is implemented, this check
  is a no-op and deletion is unconditionally allowed** — see the TODO under §Service Lines above
  and [timesheet.md](timesheet.md#open-questions). On a `closed` parent project, the line is
  fully read-only (no add/edit/delete, including no soft-delete). See the Edit/delete rules
  under §Service Lines above.
- Otherwise not specified in the original draft beyond field presence. Candidates worth deciding
  explicitly: `quantity > 0`, `unit_price >= 0`, whether a service line needs at least one
  assigned consultant before a `draft` project can move to `active`.

#### UOM enum

`Label` is what the UI displays (the Service Line table and its add/edit modal's unit
selector), following the same value → label display convention as `id_type`/`address_type` in
[company.md](company.md#21-id_type-enum), translated per this project's i18n rules (see
[frontend.md](../architecture/frontend.md#internationalization-i18n)) — the raw `Value` is never
shown to the user.

| Value    | Label   |
| ---------- | --------- |
| `hours`     | Hours     |
| `days`       | Days      |
| `ea`          | Each      |

`ea` (lowercase) — consistent casing with `hours`/`days` now that all three have a proper
display `Label` rather than relying on the raw value being shown as-is.

### Calculated values

- Each `Service Line` has a `value`, calculated as `quantity` × `unit_price`.
- Each `Project` has a `total value`, calculated as the sum of its service lines' `value`.
- **Where shown**: not on the Projects List Screen (no `total value` column there) — instead,
  both values are surfaced in the Project Form (`New`/`Edit`/`Duplicate`): each Service Line row
  shows its own `value`, and the form shows the project's `total value` (presumably a running,
  live-updating total as lines are added/edited, though that's not explicitly confirmed). See
  §Service Lines and §Project Form above.
- **Confirmed computed-at-read**: neither `value` nor `total value` is stored — no column for
  either on `Service Line`/`Project`. Both are calculated on the fly whenever displayed, per
  this project's BCNF convention (see
  [database.md](../architecture/database.md#schema-conventions)) of not persisting a purely
  derived value absent a documented performance reason.
- **Display formatting**: numbers are never shown with all the decimal places their
  underlying storage type allows — quantity and monetary amounts follow two different rules:
  - `quantity` (`NUMERIC(12, 5)` — see §Service Line entity above): decimals appear **only
    when needed**, up to 5 places, never padded with trailing zeros. E.g. `1.5`, not `1.50000`;
    a whole number shows with no decimal point at all, e.g. `10`, not `10.00000`.
  - `unit_price`, a Service Line's `value`, and a Project's `total value` are all monetary
    amounts: grouped thousands (comma-separated) and a decimal point, always showing **exactly**
    the number of decimal places given by the project's `invoicing_currency`'s `minor_unit` (see
    §Currency above and [database.md](../architecture/database.md#currencies)) — never more,
    never fewer, regardless of whether the underlying value happens to be a whole number. This
    is **not** the raw `NUMERIC` column's scale, and unlike `quantity`, trailing zeros are
    **kept**, not trimmed. E.g. for a `USD` amount (`minor_unit = 2`): `72,000.00`, not
    `72000.00000` and not `72,000`; for a `JPY` amount (`minor_unit = 0`, no decimal currency):
    `49,000,000`, not `49000000.00000`.
  - This comma/dot grouping is the current fixed format (matching the app's English-only
    state — see [frontend.md](../architecture/frontend.md#internationalization-i18n)); revisit
    if/when a second locale with different grouping conventions is actually added.

## Open Questions

- **`project_manager` assignment — deliberately deferred, not yet specified**: introduced
  alongside the `project_admin`/`project_manager` role split (see
  [user.md § Entity](user.md#entity)), a project must be able to have "one or more
  `project_manager`s assigned" so that role's `Validation`/timesheet-locking authority can be
  scoped to specific projects rather than being global. Two sub-questions are confirmed already
  (see below); the mechanism itself is intentionally left for later, separate design work:
  - **Data model**: presumed a Project↔User many-to-many, mirroring `Service Line.users`
    (see §2. Entity: `Service Line` above) — not yet added to §Project Schema. **Left open for
    now, by design.**
  - **Where it's edited**: presumed a picker on the Project form, analogous to the Service Line
    `Consultants` picker (see §Service Lines above), filtered to active `project_manager`-role
    users — not yet added to §Project Form. **Left open for now, by design.**
  - **Write access — resolved**: `project_admin`-only. `project_admin` is already the only role
    that can edit a project at all, so assigning `project_manager`s to it is naturally scoped to
    that same role — a `project_manager` cannot assign themselves or others. See
    [user.md § Open Questions](user.md#open-questions).
  - **Empty-assignment guard — resolved**: no guard. A project can validly exist (including
    `active`) with zero `project_manager`s assigned; its timesheets simply can't be
    validated/locked by anyone until someone is assigned. This is an accepted valid state, not an
    error condition.
- See also §2. Entity: `Service Line`'s own Validation rules above for the still-open
  `quantity > 0` / `unit_price >= 0` / minimum-one-consultant questions this doc already carried
  before the `project_manager` role existed.

## Reference JSON Representation

```json
{
  "project": {
    "project_id": "3e5f9c2a-1b4d-4a3e-9f1a-7c2b8e4d6a10",
    "name": "Acme ERP Rollout — Phase 1",
    "vendor": "8f14e45f-ceea-4e30-9f39-5f5d3c1d1a11",
    "client": "1a2b3c4d-5e6f-4a3b-8c9d-0e1f2a3b4c5d",
    "invoicing_currency": "EUR",
    "project_type": "time_and_material",
    "status": "active",
    "is_active": true
  },
  "service_lines": [
    {
      "service_line_id": "9a8b7c6d-5e4f-4a3b-8c9d-1e2f3a4b5c6d",
      "name": "Discovery phase",
      "quantity": 40,
      "uom": "hours",
      "unit_price": 120.0,
      "is_active": true,
      "users": ["b1c2d3e4-f5a6-4b3c-8d9e-0f1a2b3c4d5e"]
    }
  ]
}
```
