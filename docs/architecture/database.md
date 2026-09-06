# Database Architecture — PostgreSQL

Schema conventions, migrations, and indexing rules. See also: [Backend](backend.md).

## Database Software and Version

- Target database PostgreSQL 18

## Schema Conventions

- Use SQLAlchemy 2.0 style (`select()`, typed `Mapped[...]` columns), async engine/session
- **Normalization**: schema must respect Boyce-Codd Normal Form (BCNF) — for every non-trivial
  functional dependency `X -> Y` in a table, `X` must be a superkey. When reviewing or designing
  tables, check for attributes that depend on only part of a composite key, or on another
  non-key attribute, and split them into a separate table rather than allowing the dependency
  to persist. Denormalizing for performance (e.g. a materialized/read-optimized table) is
  allowed only as an explicit, documented exception alongside the normalized source of truth —
  never as the primary schema.

## Tables

Implemented so far (source of truth: `backend/app/models/user.py`, migration
`backend/alembic/versions/0001_initial.py` — keep this section in sync as the schema evolves).

### `roles`

| Column | Type        | Constraints       | Notes                                                                 |
| ------ | ----------- | ------------------ | ---------------------------------------------------------------------- |
| id     | UUID        | PK                 |                                                                          |
| name   | VARCHAR(32) | UNIQUE, NOT NULL   | `administrator`, `project_admin`, `consultant`, `project_manager` — seeded by migration `0001` (`project_admin` was named `manager` prior to the `project_admin`/`project_manager` split — see [docs/requirements/user.md § Entity](../requirements/user.md#entity))  |

### `users`

| Column           | Type         | Constraints              | Notes                                                                                                    |
| ---------------- | ------------ | -------------------------- | ------------------------------------------------------------------------------------------------------- |
| id               | UUID         | PK                         |                                                                                                            |
| name_id          | VARCHAR(255) | UNIQUE, NOT NULL           | Login identity — a local user's email, or an SSO user's SAML `NameID` (see [auth.md](../requirements/auth.md), [user.md](../requirements/user.md)) |
| hashed_password  | VARCHAR(255) | NULL                       | Null for SSO users (`is_sso = true`); they have no local password                                        |
| is_sso           | BOOLEAN      | NOT NULL, default `false`  | Flags SSO-only accounts                                                                                   |
| full_name        | VARCHAR(255) | NOT NULL                   |                                                                                                            |
| is_active        | BOOLEAN      | NOT NULL, default `true`   | Soft-delete flag (see [user.md](../requirements/user.md)) — users are deactivated, not hard-deleted       |
| theme_preference | VARCHAR(10)  | NOT NULL, default `'system'`, `CHECK (theme_preference IN ('light', 'dark', 'system'))` | See [home.md](../requirements/home.md#appearance) — a plain column, not a separate table: it's a single-valued attribute fully dependent on the user's key, so it's already in BCNF |
| created_at       | TIMESTAMPTZ  | NOT NULL, default `now()`  |                                                                                                            |

### `user_roles` (join table)

| Column  | Type | Constraints                          |
| ------- | ---- | -------------------------------------- |
| user_id | UUID | PK, FK → `users.id` (`ON DELETE CASCADE`) |
| role_id | UUID | PK, FK → `roles.id` (`ON DELETE CASCADE`) |

Many-to-many between `users` and `roles` — a user can hold multiple roles (see
[user.md](../requirements/user.md)). The composite primary key `(user_id, role_id)` satisfies
BCNF: it's the only candidate key, and there are no non-key attributes on this table to create
a dependency violation.

### `companies`, `party_identifiers`, `addresses`

Implemented (source of truth: `backend/app/models/company.py`, migration
`backend/alembic/versions/0001_initial.py`). Derived from the Peppol/UBL-driven domain model
in [company.md](../requirements/company.md#company-schema). Field names below are adapted to
Ifrit's conventions used elsewhere in this file: bare `id` primary keys (not `company_id` /
etc. as in company.md's illustrative DDL), `VARCHAR` + `CHECK` for small fixed enums (matching
`theme_preference` above) rather than native Postgres `ENUM` types, and UUID PKs generated
SQLAlchemy-side (`default=uuid.uuid4`, matching `roles`/`users`) rather than
`DEFAULT gen_random_uuid()`.

#### `companies`

| Column                     | Type         | Constraints                                              | Notes                                                                 |
| --------------------------- | ------------ | ----------------------------------------------------------- | ----------------------------------------------------------------------- |
| id                           | UUID         | PK                                                            |                                                                           |
| is_vendor                    | BOOLEAN      | NOT NULL, default `false`                                       | Ifrit-specific, not part of Peppol/UBL. Every company is implicitly usable as a project's `client`; `is_vendor` additionally marks it as selectable as a project's `vendor` (see [company.md](../requirements/company.md), [project.md](../requirements/project.md)). A company can be both a project's vendor and its client (inter-company/self-billing) — intentional. |
| legal_name                   | VARCHAR(255) | NOT NULL                                                       |                                                                           |
| trading_name                  | VARCHAR(255) | NULL                                                            |                                                                           |
| legal_form                    | VARCHAR(50)  | NULL                                                             | e.g. `Ltd`, `GmbH`, `SA`                                                  |
| country_of_registration        | CHAR(2)      | NOT NULL                                                          | ISO 3166-1 alpha-2                                                         |
| is_active                      | BOOLEAN      | NOT NULL, default `true`                                            | Soft-delete flag, same pattern as `users.is_active`                        |
| created_at                     | TIMESTAMPTZ  | NOT NULL, default `now()`                                             |                                                                              |
| updated_at                     | TIMESTAMPTZ  | NOT NULL, default `now()`                                              | Unlike `users`, which has no `updated_at` yet                               |

#### `party_identifiers`

| Column       | Type         | Constraints                                                                     | Notes                                                                    |
| ------------- | ------------ | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| id             | UUID         | PK                                                                                    |                                                                               |
| company_id      | UUID         | NOT NULL, FK → `companies.id` (`ON DELETE CASCADE`)                                    |                                                                               |
| id_type          | VARCHAR(20)  | NOT NULL, `CHECK (id_type IN ('legal_registration', 'vat', 'peppol_participant', 'duns', 'gln', 'internal'))` | See company.md §2.1                                                            |
| scheme_id         | VARCHAR(10)  | NULL                                                                                    | Required (app-level) for `legal_registration`/`peppol_participant` — ISO 6523 ICD / EAS code |
| id_value           | VARCHAR(255) | NOT NULL                                                                                 | For `vat`, includes the ISO country prefix — see company.md §2.2                 |
| is_primary          | BOOLEAN      | NOT NULL, default `false`                                                                 |                                                                                    |
| valid_from           | DATE         | NULL                                                                                        |                                                                                    |
| valid_to             | DATE         | NULL                                                                                          | Null = currently valid                                                            |

Unique index on `(company_id, id_type, COALESCE(scheme_id, ''), id_value)` — no duplicate
identical identifiers per company (see company.md §2 Validation rules). A plain
`UNIQUE(company_id, id_type, scheme_id, id_value)` constraint doesn't work here: SQL treats
NULL as distinct from NULL, and `scheme_id` is NULL for most `id_type`s (e.g. `vat`), which
would let duplicate VAT numbers through — the `COALESCE` makes NULL comparable.

#### `addresses`

| Column               | Type         | Constraints                                                              | Notes                                                     |
| --------------------- | ------------ | ----------------------------------------------------------------------------- | ------------------------------------------------------------ |
| id                      | UUID         | PK                                                                               |                                                                |
| company_id               | UUID         | NOT NULL, FK → `companies.id` (`ON DELETE CASCADE`)                               |                                                                |
| address_type              | VARCHAR(15)  | NOT NULL, `CHECK (address_type IN ('registered', 'bill_to', 'ship_to', 'postal'))`   | See company.md §3.1                                            |
| line1                      | VARCHAR(255) | NOT NULL                                                                             |                                                                |
| line2                       | VARCHAR(255) | NULL                                                                                  |                                                                |
| line3                        | VARCHAR(255) | NULL                                                                                   |                                                                |
| city                          | VARCHAR(255) | NOT NULL                                                                                |                                                                |
| postal_zone                    | VARCHAR(20)  | NULL                                                                                     | Required app-level unless the country has no postal codes      |
| country_subdivision              | VARCHAR(100) | NULL                                                                                      | Required app-level for countries where it disambiguates (US, CA, AU) |
| country_code                      | CHAR(2)      | NOT NULL                                                                                   | ISO 3166-1 alpha-2 — mandatory per Peppol (`BR-11`)               |
| is_primary                         | BOOLEAN      | NOT NULL, default `false`                                                                    |                                                                |
| valid_from                          | DATE         | NULL                                                                                            |                                                                |
| valid_to                             | DATE         | NULL                                                                                             | Null = currently valid                                          |

A partial unique index enforces at most one primary address per type per company —
`UNIQUE (company_id, address_type) WHERE is_primary` (see company.md §3 Validation rules). The
API layer also checks this proactively before insert/update, so a conflict is rejected with a
clear error rather than surfacing this index's raw constraint-violation error.

`id_type` and `address_type` use `VARCHAR` + `CHECK` rather than a lookup table for now, since
each is a small, currently-fixed set (mirrors `theme_preference` above). company.md flags that
either may grow (e.g. `REMIT_TO`); if that churn actually materializes, promote it to a lookup
table (the `roles` pattern) instead of repeatedly widening the `CHECK` constraint.

#### Reference: Peppol-spec DDL (original field naming)

The tables above are Ifrit's adapted schema. This is the literal DDL from the Peppol/UBL
domain spec — kept for cross-referencing that spec directly (`company_id`/`identifier_id`/
`address_id` PKs, native Postgres `ENUM` types, `gen_random_uuid()`) rather than as something
to implement as-is. Deliberately does **not** include `is_vendor`/`is_active` — those are
Ifrit-specific and only exist in the adapted `companies` table above; this block is the
unmodified external spec.

```sql
CREATE TABLE company (
    company_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name                 TEXT NOT NULL,
    trading_name                TEXT,
    legal_form                  TEXT,
    country_of_registration     CHAR(2) NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE identifier_type AS ENUM (
    'LEGAL_REGISTRATION', 'VAT', 'PEPPOL_PARTICIPANT',
    'DUNS', 'GLN', 'INTERNAL'
);

CREATE TABLE party_identifier (
    identifier_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES company(company_id),
    id_type         identifier_type NOT NULL,
    scheme_id       TEXT,
    id_value        TEXT NOT NULL,
    is_primary      BOOLEAN DEFAULT false,
    valid_from      DATE,
    valid_to        DATE,
    UNIQUE (company_id, id_type, scheme_id, id_value)
);

CREATE TYPE address_type AS ENUM (
    'REGISTERED', 'BILL_TO', 'SHIP_TO', 'POSTAL'
);

CREATE TABLE address (
    address_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id             UUID NOT NULL REFERENCES company(company_id),
    address_type            address_type NOT NULL,
    line1                    TEXT NOT NULL,
    line2                    TEXT,
    line3                    TEXT,
    city                     TEXT NOT NULL,
    postal_zone              TEXT,
    country_subdivision      TEXT,
    country_code             CHAR(2) NOT NULL,
    is_primary               BOOLEAN DEFAULT false,
    valid_from               DATE,
    valid_to                 DATE
);
```

### `currencies`

Implemented (source of truth: `backend/app/models/currency.py`, migration
`backend/alembic/versions/0001_initial.py`). Full ISO 4217 list, driven by the currency
selection needs of [project.md](../requirements/project.md). Covers ISO 4217's active national
currencies plus the precious-metal codes (`XAU`/`XAG`/`XPD`/`XPT`); the more obscure
bond-market/testing codes (`XDR`, `XTS`, `XXX`, `XBA`-`XBD`, `XSU`, `XUA`) are not seeded.

| Column       | Type         | Constraints                | Notes                                                                                          |
| ------------- | ------------ | ----------------------------- | -------------------------------------------------------------------------------------------------- |
| alpha_code     | CHAR(3)      | PK, NOT NULL                    | 3-letter ISO 4217 code (e.g. `USD`, `EUR`, `JPY`)                                                    |
| numeric_code    | CHAR(3)      | UNIQUE, NOT NULL                 | 3-digit ISO 4217 numeric code (e.g. `840` for USD)                                                    |
| name             | VARCHAR(100) | NOT NULL                          | Official currency name (e.g. "US Dollar")                                                              |
| minor_unit        | SMALLINT     | NULL                                | Number of decimal places (e.g. 2 for USD, 0 for JPY, 3 for BHD); NULL for currencies with no minor unit (e.g. XAU) |
| symbol             | VARCHAR(10)  | NULL                                 | Common display symbol (e.g. `$`, `€`, `¥`) — not part of ISO 4217 itself, added for display purposes    |
| is_active           | BOOLEAN      | NOT NULL, default `true`              | Whether the code is currently active/in circulation — ISO 4217 also lists historical/withdrawn codes     |
| is_enabled           | BOOLEAN      | NOT NULL, default `false`              | Restricts the full ISO 4217 list down to the subset actually selectable in the app (see seed list below)  |

`alpha_code` is the primary key; `numeric_code` is the table's other candidate key. Every other
column depends on the whole of one key or the other, not part of a composite key or a non-key
attribute, so this satisfies BCNF trivially.

The table is seeded with the full ISO 4217 list (seed data lives in the migration/a static data
file, not enumerated row-by-row here). At seed time, `is_enabled = true` for exactly:

`USD`, `EUR`, `JPY`, `GBP`, `CNY`, `AUD`, `CAD`, `CHF`, `HKD`, `SGD`

— every other currency ships with `is_enabled = false` (the column default), selectable later by
flipping the flag rather than a schema change.

### `projects`, `project_managers`, `service_lines`, `service_line_consultants`

Implemented (source of truth: `backend/app/models/project.py`, migration
`backend/alembic/versions/0001_initial.py`). Derived from [project.md](../requirements/project.md#project-schema).

#### `projects`

| Column              | Type        | Constraints                                                             | Notes                                                                                                     |
| -------------------- | ----------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| id                    | UUID        | PK                                                                            |                                                                                                                |
| name                   | VARCHAR(255) | NOT NULL                                                                       | No uniqueness constraint (see project.md §1 Validation rules)                                                  |
| vendor_company_id       | UUID        | NOT NULL, FK → `companies.id`                                                   | Must reference a company with `is_vendor = true` — app-level check, not a DB constraint                          |
| client_company_id        | UUID        | NOT NULL, FK → `companies.id`                                                     | Any company — can be the same row as `vendor_company_id` (inter-company/self-billing), intentional                |
| invoicing_currency         | CHAR(3)     | NOT NULL, FK → `currencies.alpha_code`                                              | Must reference a currency with `is_enabled = true` — app-level check                                                |
| project_type                | VARCHAR(20) | NOT NULL, `CHECK (project_type IN ('time_and_material', 'fixed_price', 'capped_tm'))` | See project.md §Project Type enum                                                                                     |
| status                        | VARCHAR(10) | NOT NULL, default `'draft'`, `CHECK (status IN ('draft', 'active', 'closed'))`           | Transitions are unrestricted (any → any) — see project.md §Status enum                                                 |
| is_active                       | BOOLEAN     | NOT NULL, default `true`                                                                    | Soft-delete flag, **independent of `status`** — unlike `companies`, deactivated projects are filtered out of the list entirely, not shown with an Active/Inactive indicator |
| created_at                        | TIMESTAMPTZ | NOT NULL, default `now()`                                                                       |                                                                                                                             |
| updated_at                          | TIMESTAMPTZ | NOT NULL, default `now()`                                                                          |                                                                                                                             |

Indexes on `vendor_company_id` and `client_company_id` support the list screen's company-name
joins. `vendor_company_id`/`client_company_id` are two separate FKs to the same `companies`
table (not a composite/self-referencing key) — each depends on the whole of the single-column
`id` PK, so this satisfies BCNF trivially.

#### `project_managers` (join table)

| Column     | Type | Constraints                                |
| ----------- | ---- | --------------------------------------------- |
| project_id   | UUID | PK, FK → `projects.id` (`ON DELETE CASCADE`)     |
| user_id       | UUID | PK, FK → `users.id` (`ON DELETE CASCADE`)          |

Many-to-many between `projects` and `users` — the users assigned to review/lock a project's
consultants' submitted timesheets via the (not yet built) Validation screen (see
[project.md § Project Managers](../requirements/project.md#project-managers) and
[user.md § Entity](../requirements/user.md#entity) for the `project_manager` role this gates
eligibility against). Same shape and same BCNF reasoning as `service_line_consultants` below —
the composite PK is the only candidate key. Only reflects *current* assignment, not history; the
API layer enforces that an assigned user actually holds the `project_manager` role and is
active, same pattern as `service_line_consultants`' `consultant` check.

#### `service_lines`

| Column     | Type            | Constraints                                                 | Notes                                                                                 |
| ----------- | ----------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| id           | UUID              | PK                                                                 |                                                                                            |
| project_id    | UUID              | NOT NULL, FK → `projects.id` (`ON DELETE CASCADE`)                    |                                                                                            |
| name           | VARCHAR(255)      | NULL                                                                     | See [project.md](../requirements/project.md#2-entity-service-line). No uniqueness constraint, may be empty; exists solely so a consultant assigned to more than one line on the same project can tell them apart when logging time |
| quantity       | NUMERIC(12, 5)    | NOT NULL                                                                | Does not depend on `uom` — same decimal shape regardless of unit type                       |
| uom             | VARCHAR(10)       | NOT NULL, `CHECK (uom IN ('hours', 'days', 'ea'))`                        | See project.md §UOM enum                                                                      |
| unit_price       | NUMERIC(14, 4)    | NOT NULL                                                                    | Denominated in the parent project's `invoicing_currency` — no separate per-line currency field |
| is_active         | BOOLEAN           | NOT NULL, default `true`                                                     | Soft-delete flag — see project.md §Validation rules. No UI to recover a deleted line             |

A partial index `(project_id) WHERE is_active` backs every query that lists a project's service
lines (the app never queries soft-deleted lines) — mirrors `addresses`' partial unique index
above, though this one isn't unique, just a targeted lookup index. `value` (`quantity ×
unit_price`) and the project's `total value` are **not** stored columns — computed at read time
(see project.md §Calculated values and the Normalization rule above).

#### `service_line_consultants` (join table)

| Column          | Type | Constraints                                     |
| ---------------- | ---- | -------------------------------------------------- |
| service_line_id   | UUID | PK, FK → `service_lines.id` (`ON DELETE CASCADE`)     |
| user_id            | UUID | PK, FK → `users.id` (`ON DELETE CASCADE`)               |

Many-to-many between `service_lines` and `users` — the consultants assigned to log time against
a line (see project.md §Service Lines). Same BCNF reasoning as `user_roles` above: the composite
PK is the only candidate key, no non-key attributes to create a dependency violation. The API
layer enforces that an assigned user actually holds the `consultant` role and is active — not a
DB constraint, since role membership itself lives in `user_roles`, not on this table.

### `time_entries`

Implemented (source of truth: `backend/app/models/time_entry.py`, migration
`backend/alembic/versions/0001_initial.py`). Derived from
[timesheet.md](../requirements/timesheet.md#data-model) — the table both the My Timesheet
(clocking) and Validation (project_manager lock/unlock, not yet built) screens are built on.

| Column           | Type        | Constraints                                                                                   | Notes                                                                                                                                                                                                                                                    |
| ----------------- | ----------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| id                 | UUID        | PK                                                                                                  |                                                                                                                                                                                                                                                             |
| user_id             | UUID        | NOT NULL, FK → `users.id` (`ON DELETE CASCADE`)                                                       | A time entry's primary subject is the person who logged it — deleting them deletes their entries, same pattern as every other child-table FK to `users` in this file except `last_updated_by` below                                                        |
| service_line_id      | UUID        | NOT NULL, FK → `service_lines.id` (`ON DELETE CASCADE`)                                                 | A time entry can't outlive the service line it was logged against                                                                                                                                                                                            |
| date                  | DATE        | NOT NULL                                                                                                  | The day the time was logged on — no time-of-day component                                                                                                                                                                                                     |
| time_entry             | INTERVAL    | NOT NULL, `CHECK (time_entry >= interval '0' AND time_entry <= interval '24:00:00')`                        | The duration logged (e.g. `01:00:00` for 1H). An earlier draft used `TIME` instead, reasoning its natural `24:00:00` ceiling would enforce the domain constraint for free — that held at the SQL level but not through this project's driver: `asyncpg` binds/decodes `TIME` exclusively via Python's `datetime.time`, whose `hour` is capped at 23, so `24:00:00` (a value the app-level range explicitly allows) could be written *or* read back but not both. `INTERVAL` round-trips through `asyncpg`/`datetime.timedelta` with no such landmine; the `CHECK` does explicitly what `TIME`'s ceiling was meant to do implicitly. Named `time_entry`, not the bare `time`/`interval`, to avoid colliding with either as a reserved-sounding identifier. The 0.5-increment rule (see timesheet.md §Interactions & Input Rules) is enforced at the API level, not a `CHECK` — same app-level-only pattern as `companies.country_of_registration`'s length check |
| comment                 | TEXT        | NULL                                                                                                        | Unused in the current UI — deliberate scope-fencing for a later iteration                                                                                                                                                                                       |
| last_updated_by           | UUID        | NULL, FK → `users.id` (`ON DELETE SET NULL`)                                                                  | **Deliberately not `CASCADE`**, unlike `user_id` above: this just records who last touched the row (e.g. a project_manager's lock/unlock), not whose data it is — deleting that project_manager should never delete someone else's time entry as a side effect. Updates on *any* row change, including a lock/unlock that only touches `is_locked`                              |
| created_at                 | TIMESTAMPTZ | NOT NULL, default `now()`                                                                                       |                                                                                                                                                                                                                                                                     |
| updated_at                   | TIMESTAMPTZ | NOT NULL, default `now()`                                                                                         |                                                                                                                                                                                                                                                                     |
| is_locked                     | BOOLEAN     | NOT NULL, default `false`                                                                                           | Set only by the (not yet built) Validation screen — the consultant's own blur-save path can never set this `true`                                                                                                                                                    |

`UNIQUE (user_id, service_line_id, date)` — a user can only log one entry per service line per
day (see timesheet.md's Implication 1: this is a deliberate simplicity trade-off, not
fine-grained enough to represent e.g. two separate sessions on the same line in one day).
Postgres backs that constraint with a supporting index automatically; a second index,
`(user_id, date)`, supports the actual query both timesheet screens run constantly — "this
user's entries across a date range" — without needing `service_line_id` up front. Every column
depends on the whole of the `id` PK (or, for the uniqueness rule, the whole of the
`(user_id, service_line_id, date)` candidate key) — no partial or transitive dependencies, so
this satisfies BCNF trivially.

## Migrations (Alembic)

- Every schema change ships with an Alembic migration in the same PR — never rely on
  `create_all`/autogenerate to reach production
- Never edit an Alembic migration that has already been merged; write a new one
- Migrations live in `backend/alembic/`; commands run from `backend/` — see
  [Backend Development Commands](backend.md#development-commands)

**Pre-release exception (current phase):** this repo is private and pre-release — no tagged
release exists yet and no production data has ever been migrated. Until the first tagged
release, every schema change is folded into the single `0001_initial.py` migration in place,
rather than adding `0002_...py`, `0003_...py`, etc. This is a deliberate, temporary departure
from the "never edit a merged migration" rule above, not a mistake or an accidental drift from
it — squashing avoids accumulating a long, noisy pre-release migration chain that nobody will
ever need to step through incrementally, since nothing has been deployed against the earlier
states yet. **The rule above is the real, permanent policy** and takes effect from the first
tagged release onward: once this repo has shipped a release (and, in particular, once any real
environment holds data migrated by `0001_initial.py`), editing it in place becomes unsafe in the
usual way (existing deployments have already applied it; rewriting it out from under them breaks
`alembic upgrade`'s checksum/history assumptions) and every subsequent schema change must be its
own new migration file, no exceptions.

## Query Patterns

- Use transactions (`async with session.begin():`) for any multi-statement write

```python
from sqlalchemy import select
from app.models.event import Event

async def get_events(session: AsyncSession, limit: int = 100) -> list[Event]:
    result = await session.execute(
        select(Event).order_by(Event.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
```

## Indexing Rules

<!-- TODO: define indexing conventions as query patterns emerge. -->



