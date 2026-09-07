# Company — Data Model & User Stories

Defines the `Company` entity used on projects, plus the identifiers and addresses it needs to
be Peppol/UBL-compliant for invoicing. Inferred/drafted — review and adjust before treating as
final. See also [project.md](project.md).

**Client/vendor model:** every company is implicitly usable as the billed entity (`client`) on
a project, at all times. `is_vendor` is an additional capability flag — only `is_vendor = true`
companies are selectable as a project's vendor. This deliberately allows the same company to be
selected as both vendor and client on a project, to support inter-company/self-billing.

**Compliance target:** Peppol BIS Billing 3.0 / EN 16931 (drives the Company Schema section
below).

The schema in this document is the domain model — field names here follow Peppol/UBL
terminology for cross-referencing the spec. The actual implemented tables (Ifrit's naming
conventions, exact types, constraints) live in
[database.md](../architecture/database.md#tables) and are the authoritative source once
implemented; this doc explains the *why* behind them.

## User Stories

- As an administrator, I want to create a company and optionally flag it as a `vendor`, so that
  it can be selected as a project's vendor — every company is already selectable as a project's
  client, with no flag needed.
- As an administrator, I want to edit company details, so that records stay accurate over time.
- As a project_admin, I want to select an existing vendor-flagged company as a project's vendor,
  and any company (including that same vendor) as its client, so that I don't have to re-enter
  company data per project, and can represent inter-company/self-billing when it happens.
- As an administrator, I want to record a company's legal/VAT/Peppol identifiers and its
  addresses (registered, billing, shipping), so that invoices generated for that company are
  Peppol/UBL-compliant without manual rework at export time.
- As an administrator, I want a company to support multiple ship-to addresses and multiple
  identifiers, so that companies with several warehouses or multiple registries (e.g. VAT +
  Peppol participant ID) are represented correctly rather than forced into single fields.
- As an administrator, I want to create a new company via a clearly visible "+" action on the
  companies list, so that adding one is a single obvious step.
- As an administrator, I want to edit an existing company's details from the companies list, so
  that I can correct or update its record.
- As an administrator, I want to duplicate an existing company as the starting point for a new
  one, so that I don't have to re-enter shared details (e.g. country, legal form) for similar
  companies.
- As an administrator, I want to delete a company, understanding that this deactivates it
  (`is_active = false`) rather than removing the row, so that companies already referenced by a
  project keep their referential integrity.
- As an administrator, I want to quickly search the companies list by legal name, so that I can
  find a specific company without scrolling through all of them.

## Companies List Screen

The `companies` screen under `configuration` (see [home.md](home.md#navigation)). A Data Table:

- **Header**: shadcn/ui's native Data Table filter component (not a custom search
  implementation) filtering by `legal_name` as the administrator types, and a **`+`** button
  that opens the create-company flow.
- **Columns**: `legal_name`, `country_of_registration`, status (`is_active`, shown as an
  Active/Inactive indicator, not a raw boolean), and a trailing actions column (not sortable).
  Every other column is sortable, server-side (see
  [Projects List Screen § API contract: sorting](project.md#api-contract-sorting), which this
  screen shares), via the same shared `DataTableColumnHeader` used by
  [Projects](project.md#projects-list-screen) — see
  [frontend.md](../architecture/frontend.md#component-patterns).
- **Row actions**: an **`…`** button opens a dropdown menu with, in order: `Edit`,
  `Duplicate`, a separator, then `Delete` — `Delete` is styled in red/destructive to signal
  it's a different class of action from `Edit`/`Duplicate`, even though it's a deactivation
  rather than a hard delete (see the Delete user story above). Like every destructive action
  app-wide, `Delete` requires a confirmation dialog before executing (see
  [frontend.md](../architecture/frontend.md#destructive-actions)). There is currently no UI to
  reactivate a deactivated company — `Delete` is a one-way action for now.
- **Pagination**: 50 companies per page, with `Previous`/`Next` controls — no jump-to-page or
  page-number list.

## Company Form (Create / Edit / Duplicate)

`New`, `Edit`, and `Duplicate` (triggered from the companies list above) all open the same
form. Party Identifiers and Addresses (below) are sub-sections **within** this one form — not
separate screens or panels sitting outside it.

- **`New`**: blank form.
- **`Edit`** / **`Duplicate`**: pre-filled with the source company's current field values,
  including its `PartyIdentifier`/`Address` children (see Duplicate behavior below).
- The form stays close to the data model — it simply exposes `Company`'s fields (§1 below)
  directly, rather than grouping or wizarding them. `is_active` is **not** one of the exposed
  fields — it's never edited from this form, only ever set by the `Delete` action on the
  companies list (see above).
- **Footer actions**: at the **bottom of the whole form** — after the §1 fields *and* after the
  Party Identifiers/Addresses sections, not sandwiched between them — a **`Save`** button, and
  a separate **`Close`** button in the bottom-left corner that returns to the companies list
  without saving. This is the conventional position for form actions; they don't float above
  unrelated content partway down the form.
- `Duplicate` copies the source company's fields **and** all of its `PartyIdentifier`/
  `Address` children. Since identifiers like `VAT`/`LEGAL_REGISTRATION` are meant to uniquely
  identify one real legal entity, saving a duplicated company without changing its copied
  identifiers should be caught by validation and rejected with feedback, rather than silently
  creating two companies claiming the same identifier — see the broader field-validation topic
  flagged in Open Questions.

### Creating a new company's identifiers/addresses (auto-save)

Party Identifiers and Addresses are always shown as normal Data Tables within the form (see
below) — including on a brand-new, not-yet-saved company. There is no "save the company first"
placeholder message; a not-yet-saved company's tables just start empty, same as any other
empty state.

A `PartyIdentifier`/`Address` row can only be attached to a persisted `Company` (it needs a
real `company_id` to attach to), so this has to be handled gracefully rather than blocking the
user with an explanation. On a **not-yet-saved** company, clicking **`+`** on either table:

1. Validates the form's required fields (at minimum `legal_name`). If invalid, shows the
   validation error on the form (e.g. "Legal name is required") the same way `Save` would, and
   does not proceed.
2. If valid, silently saves the company first — same effect as clicking `Save` — obtaining its
   `company_id`.
3. Then opens the add-identifier/add-address modal as normal.

For an already-saved company (`Edit`, or a `New` company past its first save), **`+`** just
opens the modal directly — no extra save step.

### Party Identifiers

- Labeled **"Party Identifiers"**, a sub-section within the Company form.
- A Data Table listing the company's `PartyIdentifier` rows (§2 below) — see "Creating a new
  company's identifiers/addresses" above for what `+` does before the company is first saved.
- A **`+`** button opens a modal to add a new identifier; on save, it appears in the list
  immediately.
- The table displays each identifier's **label**, not its raw value (e.g. "Legal
  Registration", not `legal_registration`) — see §2.1 for the value → label mapping. The
  add/edit modal's type selector uses the same labels.
- Each row has a **`…`** action button with `Edit`, `Duplicate`, and `Delete` (same
  destructive-action confirmation rule as everywhere else — see
  [frontend.md](../architecture/frontend.md#destructive-actions)). `Delete` here is a **hard
  delete**, same as `Address` below — the row is actually removed, not soft-invalidated via
  `valid_to`.

### Addresses

- Labeled **"Addresses"** — same pattern as Party Identifiers: always a normal Data Table of
  the company's `Address` rows (§3 below) within the Company form, a **`+`** button opening a
  modal to add a new address (see "Creating a new company's identifiers/addresses" above), and
  a **`…`** row action with `Edit`, `Duplicate`, and `Delete`. `Delete` here is a **hard
  delete** — the row is actually removed, not soft-invalidated via `valid_to`.
- The table displays each address's **type label**, not its raw value (e.g. "Ship To", not
  `ship_to`) — see §3.1 for the value → label mapping. The add/edit modal's type selector uses
  the same labels.
- `Duplicate` is particularly useful here: `REGISTERED`, `BILL_TO`, and `SHIP_TO` are often
  identical for a company. Duplicating an existing address pre-fills a new row so the
  administrator only has to change `address_type` (and `is_primary`), instead of retyping the
  same lines/city/postal code/country.

## Company Schema

Three entities:

1. **Company** — the legal entity itself, plus the `is_vendor` flag Ifrit needs for project
   assignment (not part of Peppol/UBL — Ifrit-specific, see the `is_vendor` row below)
2. **PartyIdentifier** — one-to-many identifiers belonging to a company (VAT, registration
   number, Peppol participant ID, etc.)
3. **Address** — one-to-many addresses belonging to a company, distinguished by type
   (registered, bill-to, ship-to, ...)

```
Company (1) ──< PartyIdentifier (N)
Company (1) ──< Address (N)
```

Identifiers and addresses are **not** columns on the Company row. A company can legitimately
have multiple ship-to addresses (multiple warehouses) and multiple identifiers of different
types issued by different registries — modeling these as child tables avoids schema churn,
matches how Peppol itself represents parties, and keeps the schema in BCNF (see
[database.md](../architecture/database.md#schema-conventions)): a repeating group of
identifiers/addresses crammed into columns on `Company` would violate it. There's no cached
"primary VAT" or "primary registered address" on `Company` either — keep it simple, joining to
`PartyIdentifier`/`Address` when needed is fine.

### 1. Entity: `Company`

Represents the legal entity.

| Field | Type | Required | Notes |
|---|---|---|---|
| `company_id` | UUID / surrogate key | Yes | Primary key |
| `is_vendor` | boolean | Yes | Ifrit-specific — not part of Peppol/UBL. Default `false`. Every company is implicitly selectable as a project's `client` at all times (no flag needed); `is_vendor` additionally marks it as selectable as a project's `vendor`. See [project.md](project.md). |
| `legal_name` | string | Yes | Full registered legal name |
| `trading_name` | string | No | DBA / trade name, if different from legal name |
| `legal_form` | string | No | e.g. `Ltd`, `GmbH`, `SA`, `Pte Ltd` |
| `country_of_registration` | string(2) | Yes | ISO 3166-1 alpha-2 |
| `is_active` | boolean | Yes | Soft-delete flag, default `true` — same pattern as `User` (see [user.md](user.md)); preserves referential integrity for companies already referenced by a project |
| `created_at` | timestamp | Yes | Record creation |
| `updated_at` | timestamp | Yes | Record last modified |

> Note: `legal_registration_id`, `vat_number`, and `peppol_participant_id` deliberately do
> **not** live on this table. See §2 — they are represented as typed identifiers in
> `PartyIdentifier` so the model can hold multiple identifiers per type/scheme without
> migration.

#### Validation rules

- `legal_name` must not be empty.
- `country_of_registration` must be a valid ISO 3166-1 alpha-2 code.
- A company intended to act as a **Seller** in Peppol transactions must have at least one of: a
  `LEGAL_REGISTRATION` identifier, a `VAT` identifier, or a generic `SELLER_ID` identifier
  present in `PartyIdentifier` (Peppol BIS rule: buyer must be able to automatically identify
  the supplier via one of these).

### 2. Entity: `PartyIdentifier`

Represents a single identifier belonging to a company. A company has many.

| Field | Type | Required | Notes |
|---|---|---|---|
| `identifier_id` | UUID / surrogate key | Yes | Primary key |
| `company_id` | FK → Company | Yes | |
| `id_type` | enum | Yes | See §2.1 |
| `scheme_id` | string | Yes (for `LEGAL_REGISTRATION`, `PEPPOL_PARTICIPANT`) | ISO 6523 ICD code or EAS code — see §2.2 |
| `id_value` | string | Yes | The raw identifier value |
| `is_primary` | boolean | No | Disambiguates when multiple of same type exist |
| `valid_from` | date | No | Optional history/audit tracking |
| `valid_to` | date | No | Null = currently valid |

#### 2.1 `id_type` enum

`Label` is what the UI displays (list, and the add/edit modal's type selector) — the raw
`Value` is never shown to the user.

| Value | Label | Description |
|---|---|---|
| `LEGAL_REGISTRATION` | Legal Registration | National company registration number (e.g. Companies House, KVK, ACRA UEN) |
| `VAT` | VAT | VAT / GST identifier |
| `PEPPOL_PARTICIPANT` | Peppol Participant | Peppol network participant ID (used in `EndpointID`) |
| `DUNS` | DUNS | Dun & Bradstreet number |
| `GLN` | GLN | Global Location Number |
| `INTERNAL` | Internal | Internal ERP/CRM customer or vendor code |

#### 2.2 `scheme_id` — code list rules

- For `LEGAL_REGISTRATION` and `PEPPOL_PARTICIPANT`, `scheme_id` **must** be a value from the
  Peppol-approved subset of the **ISO 6523 ICD** code list (also published as the Peppol
  **Electronic Address Scheme, EAS, list**). Examples: `0088` (GLN), `0192` (Norway Org.nr),
  `0106` (Netherlands KvK), `0183` (Switzerland UIDB), `0158` (Czech Republic ICO).
- For `VAT`, store the value **including the ISO country prefix** (e.g. `BE0123456749`), never
  split into country + number. This is a hard Peppol requirement — do not "normalize" it away.
- Never concatenate `scheme_id` and `id_value` into a single string in storage. Concatenate
  only at the point of XML/UBL serialization (`schemeID` attribute + element value).

#### Validation rules

- `(company_id, id_type, scheme_id, id_value)` should be effectively unique (no duplicate
  identical identifiers).
- `scheme_id` must be validated against the current ISO 6523 ICD / Peppol EAS code list at
  write time, not just at export time.
- `id_value` for `VAT` must match the regex/format rules of the country indicated by its
  prefix.

### 3. Entity: `Address`

Represents a single address belonging to a company. A company has many, distinguished by
`address_type`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `address_id` | UUID / surrogate key | Yes | Primary key |
| `company_id` | FK → Company | Yes | |
| `address_type` | enum | Yes | See §3.1 |
| `line1` | string | Yes | Main address line |
| `line2` | string | No | Additional line |
| `line3` | string | No | Additional line |
| `city` | string | Yes | |
| `postal_zone` | string | Yes (unless country has no postal codes) | Postcode / ZIP |
| `country_subdivision` | string | Conditional | State/province/region — required for countries where it disambiguates address (e.g. US, CA, AU) |
| `country_code` | string(2) | Yes | ISO 3166-1 alpha-2 — mandatory per Peppol |
| `is_primary` | boolean | No | Disambiguates when multiple addresses share a type |
| `valid_from` | date | No | Optional history/audit tracking |
| `valid_to` | date | No | Null = currently valid |

#### 3.1 `address_type` enum

`Label` is what the UI displays (list, and the add/edit modal's type selector) — the raw
`Value` is never shown to the user.

| Value | Label | Description |
|---|---|---|
| `REGISTERED` | Registered | Registered / legal address of the entity |
| `BILL_TO` | Bill To | Billing address |
| `SHIP_TO` | Ship To | Delivery/shipping address (may be multiple per company) |
| `POSTAL` | Postal | General correspondence address, if distinct from the above |

Implement as a lookup table rather than a hardcoded enum if the list is expected to grow (e.g.
adding `REMIT_TO`, `DELIVERY_SITE` later) — avoids a schema migration for a new type. Same
tradeoff applies to `id_type` above; see [database.md](../architecture/database.md#tables) for
which approach is actually used.

#### Validation rules

- `country_code` is always mandatory and must be ISO 3166-1 alpha-2 — this is a hard Peppol
  validation rule (`BR-11` equivalent: postal address must contain a country code).
- Exactly one `line1`+`city`+`country_code` combination is mandatory per address row;
  `line2`/`line3` and `country_subdivision` are optional depending on jurisdiction.
- A company must have at least one `REGISTERED` address to be considered complete for Peppol
  export. This is an export-time check, not a save-time requirement — a company can be saved
  with zero addresses (see the Company Form section above) and completed later.
- Multiple `SHIP_TO` rows are valid and expected (e.g. multiple warehouses); use `is_primary`
  to flag a default if the consuming system needs one.
- At most one `Address` row per `(company_id, address_type)` can have `is_primary = true` —
  e.g. a company cannot have two primary `REGISTERED` addresses at once. Saving a row as
  primary when another primary of the same type already exists for that company must be
  rejected, not silently allowed (or silently un-primary the previous one).

## Peppol Compliance Checklist

Use this as an acceptance checklist when implementing export/serialization to UBL:

- [ ] Every Seller-role company has at least one of `LEGAL_REGISTRATION`, `VAT`, or a generic
      seller identifier populated.
- [ ] Every `LEGAL_REGISTRATION` / `PEPPOL_PARTICIPANT` identifier carries a valid ISO 6523 ICD
      / EAS `scheme_id`.
- [ ] Every `VAT` identifier includes the ISO country prefix.
- [ ] Every address has a non-null `country_code` (ISO 3166-1 alpha-2).
- [ ] Address lines map 1:1 to UBL `AddressLine` cardinality (1 to 3 lines).
- [ ] `scheme_id` values are validated against the current Peppol code list, not hardcoded once
      and forgotten (the list is versioned and updated).
- [ ] No identifier value is stored pre-concatenated with its scheme — scheme and value are
      always separate fields.

Reference DDL for this schema lives in
[database.md](../architecture/database.md#reference-peppol-spec-ddl-original-field-naming) —
functional requirements shouldn't hold database schema definitions; the field-level tables
above (§1–§3) are this doc's description of the model, and database.md owns the SQL.

## Reference JSON Representation

```json
{
  "company": {
    "company_id": "8f14e45f-ceea-4e30-9f39-5f5d3c1d1a11",
    "is_vendor": true,
    "legal_name": "Acme Manufacturing SA",
    "trading_name": "Acme Mfg",
    "legal_form": "SA",
    "country_of_registration": "BE"
  },
  "identifiers": [
    {
      "id_type": "LEGAL_REGISTRATION",
      "scheme_id": "0208",
      "id_value": "0123456749"
    },
    {
      "id_type": "VAT",
      "id_value": "BE0123456749"
    },
    {
      "id_type": "PEPPOL_PARTICIPANT",
      "scheme_id": "0208",
      "id_value": "0123456749"
    }
  ],
  "addresses": [
    {
      "address_type": "REGISTERED",
      "line1": "Rue de la Loi 1",
      "city": "Brussels",
      "postal_zone": "1000",
      "country_code": "BE",
      "is_primary": true
    },
    {
      "address_type": "SHIP_TO",
      "line1": "Zone Industrielle 12",
      "city": "Liège",
      "postal_zone": "4000",
      "country_code": "BE",
      "is_primary": true
    }
  ]
}
```

## Open Questions

- Should `Address` support geocoding fields (lat/long) for logistics use cases, or stay purely
  postal?
- Should identifier/address history (`valid_from`/`valid_to`) be enforced at the application
  layer or via temporal table patterns? Now that `Delete` on both entities is confirmed as a
  hard delete (see Company Form above), `valid_from`/`valid_to` is purely a historical/audit
  concern on rows that still exist — not a lifecycle/soft-delete mechanism — which narrows but
  doesn't answer this question.
- **Resolved — no cross-company identifier uniqueness, by design.** `Duplicate` copying a
  company's identifiers verbatim (see Company Form above), and later being saved unchanged, is
  **not** an error to catch. §2's uniqueness rule is deliberately scoped per-`company_id`, not
  global, and stays that way: the Peppol/UBL-shaped schema here exists so this data is in the
  *right shape* for future e-invoicing, not so this app polices real-world global uniqueness of
  VAT/registration/Peppol-participant numbers across every company record it happens to hold.
  Two companies legitimately sharing an identifier (e.g. a duplicated draft record, a
  data-entry error, a genuinely shared registration in some jurisdictions) is a data-quality
  concern for whoever operates on that data later, not a constraint this app needs to enforce —
  adding cross-company uniqueness would be real engineering complexity (locking/race handling
  across unrelated rows, a global index instead of a scoped one) in exchange for catching a
  case that isn't actually harmful to this app's own behavior.
- Do the add/edit modals for Party Identifiers and Addresses expose exactly their respective
  schema fields (§2/§3), matching the "stay close to the data model" principle stated for the
  parent form? Assumed yes, not explicitly confirmed.
- Should `PartyIdentifier` get the same "at most one primary per type" rule just added for
  `Address` (§3 Validation rules) — i.e. at most one primary identifier per `(company_id,
  id_type)`? Not currently specified either way for identifiers.
